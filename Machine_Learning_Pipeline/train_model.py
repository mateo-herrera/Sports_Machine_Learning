"""
Train and evaluate the MLB win-probability model.

Two separate jobs, deliberately kept apart:

  MEASUREMENT  -- walk-forward across seasons. Every game is predicted once by
                  a model that never saw it. This is where the honest numbers
                  come from, and the only place a feature change can be judged.

  PRODUCTION   -- one final fit on ALL available data, saved to disk for the
                  API to serve. A model trained on 80% of history is strictly
                  worse at predicting tomorrow than one trained on 100%; the
                  hold-out exists to measure, not to ship.

Feature selection runs as a chain of candidates. Each is compared against the
current incumbent with a paired bootstrap on identical games, and only replaces
it when the confidence interval actually clears zero. A change that merely
looks better is not better -- at this signal level the noise band is about
+/-0.006 AUC and it is very easy to fool yourself.
"""

import os
import warnings

import joblib

warnings.filterwarnings('ignore', category=FutureWarning)

from . import pitcher_pipeline as ppl                               # noqa: E402
from . import team_data_pipeline as tdp                               # noqa: E402
from .pitcher_pipeline import get_full_training_data              # noqa: E402
from .team_data_pipeline import get_training_data                 # noqa: E402
from .walk_forward import (                                       # noqa: E402
    calibration_table,
    compare,
    make_default_model,
    summarize,
    walk_forward,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_DIR, 'mlb_model.joblib')

MIN_YEAR = 2022            # warm-up season: seeds Elo and the pitcher windows
RUN_EXPERIMENTS = True     # set False once the feature set is settled

# Features that earlier runs showed to be redundant or noise-like:
#   days_rest              -- stable coefficient but zero unique contribution
#   win_pct_last10         -- correlates 0.81 with run_diff_last10
#   bullpen_ip             -- workload without quality carried no signal
#   prior_season_run_diff  -- superseded by Elo's offseason regression
DEAD_FEATURES = ('days_rest', 'win_pct_last10', 'bullpen_ip', 'prior_season_run_diff')


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

def load_data():
    df = get_full_training_data(get_training_data(min_year=MIN_YEAR))

    feature_cols = tdp.FEATURE_COLS + ppl.FEATURE_COLS
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        raise KeyError(f"Missing expected feature columns: {missing}")

    df = df.sort_values(['date', 'game_id']).reset_index(drop=True)

    print(f"\n{len(df)} games, seasons {df['season'].min()}-{df['season'].max()}")
    print(f"{len(feature_cols)} features")
    print(f"Home win rate: {df['home_win'].mean():.4f}")
    return df, feature_cols


def to_differences(df, feature_cols):
    """Collapse each home_X / away_X pair into a single X_diff column.

    Halves the parameter count and encodes the symmetry of the problem
    directly instead of making the model learn it from data. It also kills
    most of the collinearity that has been splitting credit between paired
    coefficients and flipping their signs.

    Sign convention: positive always means the home side has more of the
    thing. For FIP that means a positive diff FAVOURS THE AWAY TEAM, since
    lower FIP is better. The model handles it; just don't misread the
    coefficient.

    The intercept absorbs home-field advantage, which is why it stays.
    """
    stems, unpaired = [], []
    for c in feature_cols:
        if c.startswith('home_') and f'away_{c[len("home_"):]}' in feature_cols:
            stems.append(c[len('home_'):])
        elif c.startswith('away_') and f'home_{c[len("away_"):]}' in feature_cols:
            continue                      # handled by its home_ partner
        else:
            # No partner, or no side prefix at all. Carry it through as-is
            # rather than dropping it -- silent feature loss is the failure
            # mode that a substring filter caused earlier in this project.
            unpaired.append(c)

    out = df.copy()
    diff_cols = []
    for stem in stems:
        col = f'{stem}_diff'
        out[col] = out[f'home_{stem}'] - out[f'away_{stem}']
        diff_cols.append(col)

    return out, diff_cols + unpaired


# --------------------------------------------------------------------------
# Measurement
# --------------------------------------------------------------------------

def evaluate(df, feature_cols, label='baseline', full=True):
    if full:
        print("\n" + "=" * 70)
        print(f"WALK-FORWARD EVALUATION -- {label} ({len(feature_cols)} features)")
        print("=" * 70)

    result = walk_forward(df, feature_cols, verbose=full)

    if full:
        summarize(result)
        calibration_table(result)

    return result


def run_experiments(df, feature_cols, incumbent):
    """Try candidate feature sets; adopt one only if a paired test says so."""
    print("\n" + "=" * 70)
    print("EXPERIMENTS")
    print("=" * 70)

    best = {'label': 'full', 'df': df, 'cols': feature_cols, 'result': incumbent}

    lean_cols = [c for c in feature_cols
                 if not any(d in c for d in DEAD_FEATURES)]
    df_diff_full, diff_cols_full = to_differences(df, feature_cols)
    df_diff_lean, diff_cols_lean = to_differences(df, lean_cols)

    candidates = [
        ('without days_rest', df, [c for c in feature_cols if 'days_rest' not in c]),
        ('without win_pct_last10', df, [c for c in feature_cols if 'win_pct_last10' not in c]),
        ('without bullpen_ip', df, [c for c in feature_cols if 'bullpen_ip' not in c]),
        ('lean (all dead dropped)', df, lean_cols),
        ('differences, full set', df_diff_full, diff_cols_full),
        ('differences, lean set', df_diff_lean, diff_cols_lean),
    ]

    for label, cand_df, cols in candidates:
        if not cols or cols == best['cols']:
            print(f"\n[{label}] nothing to change, skipped")
            continue

        result = evaluate(cand_df, cols, label, full=False)
        stats = compare(best['result'], result,
                        labels=(best['label'], f'{label} [{len(cols)}]'))

        # Adopt only on evidence. "Looks better" is not better.
        if stats['ci'][0] > 0:
            print(f"  -> ADOPTED: {label} beats {best['label']}")
            best = {'label': label, 'df': cand_df, 'cols': cols, 'result': result}
        elif stats['ci'][1] < 0:
            print(f"  -> rejected: worse than {best['label']}")
        else:
            print(f"  -> rejected: not distinguishable from {best['label']}")

    print(f"\nWinner: {best['label']} ({len(best['cols'])} features), "
          f"pooled AUC {best['result'].pooled['auc']:.4f}")
    return best


# --------------------------------------------------------------------------
# Production fit
# --------------------------------------------------------------------------

def fit_and_save(df, feature_cols, result, uses_differences, path=MODEL_PATH):
    """Refit on everything and save atomically, with walk-forward metrics."""
    X = df[feature_cols]
    y = df['home_win'].astype(int)

    model = make_default_model()
    model.fit(X, y)

    pooled = result.pooled
    payload = {
        'model': model,
        'feature_cols': list(feature_cols),
        # The prediction path MUST apply the same transform. Without this flag
        # it would feed raw home_/away_ columns to a model expecting diffs.
        'uses_differences': uses_differences,
        'trained_through': str(df['date'].max().date()),
        'n_train': len(df),
        # Metrics come from walk-forward, NOT from this model's own training
        # data -- reporting in-sample numbers as accuracy would be dishonest.
        'metrics': {
            'auc': pooled['auc'],
            'log_loss': pooled['log_loss'],
            'brier': pooled['brier'],
            'accuracy': pooled['accuracy'],
            'baseline': pooled['baseline'],
            'n_eval': pooled['n'],
            'method': 'walk-forward by season, pooled out-of-sample',
        },
        'per_fold': result.folds.to_dict('records'),
    }

    tmp = path + '.tmp'
    joblib.dump(payload, tmp)
    os.replace(tmp, path)          # atomic: the API never reads a half-file

    print(f"\nSaved model trained on {len(df)} games through "
          f"{payload['trained_through']} -> {path}")
    print(f"Reported accuracy: {pooled['accuracy']:.4f} "
          f"(baseline {pooled['baseline']:.4f}, AUC {pooled['auc']:.4f})")
    if uses_differences:
        print("NOTE: model expects DIFFERENCE features -- the prediction "
              "pipeline must call to_differences() before predicting.")


# --------------------------------------------------------------------------

def main():
    df, feature_cols = load_data()
    result = evaluate(df, feature_cols, 'full feature set')

    best = {'label': 'full', 'df': df, 'cols': feature_cols, 'result': result}
    if RUN_EXPERIMENTS:
        best = run_experiments(df, feature_cols, result)

        if best['label'] != 'full':
            best['result'] = evaluate(best['df'], best['cols'], best['label'])

    fit_and_save(
        best['df'], best['cols'], best['result'],
        uses_differences='differences' in best['label'],
    )


if __name__ == '__main__':
    main()