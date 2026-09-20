"""
Walk-forward (rolling-origin) evaluation for the MLB win-probability model.

Why this exists
---------------
A single 80/20 chronological split on ~1,300 test games has a standard error of
roughly +/-0.017 on AUC. Most feature changes are worth ~0.01, so a single split
cannot tell you whether a change helped.

This module fixes that two ways:

1. Multiple folds -> you see whether a gain is consistent or a one-season fluke.
2. Pooled out-of-sample predictions -> every game gets predicted exactly once by
   a model that never saw it, so you can compute one AUC on ~7,000 games
   (SE ~ +/-0.007) instead of averaging noisy per-fold numbers.

It also keeps the per-game OOS predictions, which lets you do *paired*
comparisons between model variants on identical test games. A paired comparison
is far more sensitive than comparing two independent AUC estimates.

Usage
-----
    from walk_forward import make_default_model, walk_forward, summarize, compare

    result = walk_forward(df, feature_cols, make_default_model)
    summarize(result)

    # later, after changing features:
    result_v2 = walk_forward(df, feature_cols_v2, make_default_model)
    compare(result, result_v2, labels=("baseline", "with FIP"))
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegressionCV
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

TARGET = "home_win"
DATE_COL = "date"


# --------------------------------------------------------------------------
# Model factory
# --------------------------------------------------------------------------

def make_default_model():
    """A fresh, unfitted copy of the current best model.

    Must return a NEW object each call -- every fold needs a clean model, or
    you leak fitted state (and the scaler's means) across folds.
    """
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegressionCV(
            Cs=np.logspace(-4, 2, 30),
            cv=TimeSeriesSplit(n_splits=8),
            scoring="neg_log_loss",
            max_iter=2000,
        )),
    ])


# --------------------------------------------------------------------------
# Result container
# --------------------------------------------------------------------------

@dataclass
class WalkForwardResult:
    folds: pd.DataFrame           # one row per fold
    oos: pd.DataFrame             # one row per test game: date, season, y, prob
    feature_cols: list
    coefs: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def pooled(self):
        y = self.oos["y"].values
        p = self.oos["prob"].values
        baseline = max(y.mean(), 1 - y.mean())
        return {
            "n": len(y),
            "auc": roc_auc_score(y, p),
            "log_loss": log_loss(y, p),
            "brier": brier_score_loss(y, p),
            "accuracy": accuracy_score(y, (p > 0.5).astype(int)),
            "baseline": baseline,
            "pred_home_rate": (p > 0.5).mean(),
        }


# --------------------------------------------------------------------------
# Core loop
# --------------------------------------------------------------------------

def walk_forward(
    df,
    feature_cols,
    model_factory=make_default_model,
    min_train_seasons=1,
    target=TARGET,
    date_col=DATE_COL,
    verbose=True,
):
    """Expanding-window evaluation, one fold per season.

    Fold k trains on every season before season k and tests on season k.
    Nothing in a fold's training set occurs after its test set.
    """
    df = df.dropna(subset=list(feature_cols) + [target]).copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df["season"] = df[date_col].dt.year
    df = df.sort_values([date_col, "game_id"]).reset_index(drop=True)

    seasons = sorted(df["season"].unique())
    test_seasons = seasons[min_train_seasons:]

    if not test_seasons:
        raise ValueError(
            f"Need more than {min_train_seasons} season(s) of data; found {seasons}"
        )

    fold_rows, oos_frames, coef_rows = [], [], []

    for season in test_seasons:
        train = df[df["season"] < season]
        test = df[df["season"] == season]

        if len(test) == 0:
            continue

        X_train, y_train = train[feature_cols], train[target].astype(int)
        X_test, y_test = test[feature_cols], test[target].astype(int)

        model = model_factory()
        model.fit(X_train, y_train)

        prob = model.predict_proba(X_test)[:, 1]
        pred = (prob > 0.5).astype(int)
        baseline = max(y_test.mean(), 1 - y_test.mean())

        fold_rows.append({
            "test_season": season,
            "n_train": len(train),
            "n_test": len(test),
            "auc": roc_auc_score(y_test, prob),
            "log_loss": log_loss(y_test, prob),
            "brier": brier_score_loss(y_test, prob),
            "accuracy": accuracy_score(y_test, pred),
            "baseline": baseline,
            "lift": accuracy_score(y_test, pred) - baseline,
            "pred_home_rate": pred.mean(),
            "train_auc": roc_auc_score(
                y_train, model.predict_proba(X_train)[:, 1]
            ),
        })

        oos_frames.append(pd.DataFrame({
            "game_id": test["game_id"].values,
            "date": test[date_col].values,
            "season": season,
            "y": y_test.values,
            "prob": prob,
        }))

        # Track coefficient stability across folds -- a feature whose sign
        # flips between seasons is noise, not signal.
        clf = model.named_steps["clf"] if hasattr(model, "named_steps") else model
        if hasattr(clf, "coef_"):
            row = dict(zip(feature_cols, clf.coef_[0]))
            row["test_season"] = season
            if hasattr(clf, "C_"):
                row["best_C"] = float(np.atleast_1d(clf.C_)[0])
            coef_rows.append(row)

        if verbose:
            f = fold_rows[-1]
            print(
                f"  {season}: train={f['n_train']:>5}  test={f['n_test']:>5}  "
                f"AUC={f['auc']:.4f}  logloss={f['log_loss']:.4f}  "
                f"acc={f['accuracy']:.4f} (base {f['baseline']:.4f})"
            )

    return WalkForwardResult(
        folds=pd.DataFrame(fold_rows),
        oos=pd.concat(oos_frames, ignore_index=True),
        feature_cols=list(feature_cols),
        coefs=pd.DataFrame(coef_rows),
    )


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def summarize(result, show_coefs=True):
    """Print per-fold metrics, the pooled number, and coefficient stability."""
    folds = result.folds

    print("\n--- per-fold ---")
    print(folds.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n--- across folds ---")
    for metric in ("auc", "log_loss", "accuracy", "lift"):
        vals = folds[metric]
        print(f"  {metric:<10} mean={vals.mean():.4f}  sd={vals.std(ddof=1):.4f}  "
              f"min={vals.min():.4f}  max={vals.max():.4f}")

    p = result.pooled
    print(f"\n--- pooled out-of-sample (n={p['n']}) ---")
    print(f"  AUC             {p['auc']:.4f}   (SE ~ {auc_se(result.oos):.4f})")
    print(f"  Log loss        {p['log_loss']:.4f}")
    print(f"  Brier           {p['brier']:.4f}")
    print(f"  Accuracy        {p['accuracy']:.4f}   (baseline {p['baseline']:.4f})")
    print(f"  Pred home rate  {p['pred_home_rate']:.4f}")

    gap = folds["train_auc"].mean() - folds["auc"].mean()
    print(f"\n  mean train AUC  {folds['train_auc'].mean():.4f}  "
          f"(gap {gap:+.4f} -> {'overfitting' if gap > 0.03 else 'underfitting / feature-limited'})")

    if show_coefs and not result.coefs.empty:
        print("\n--- coefficient stability (sign flips = noise) ---")
        c = result.coefs.drop(columns=["test_season"], errors="ignore")
        c = c.drop(columns=["best_C"], errors="ignore")
        stab = pd.DataFrame({
            "mean": c.mean(),
            "sd": c.std(ddof=1),
            "sign_flips": (np.sign(c) != np.sign(c.mean())).sum(),
        }).sort_values("mean", key=abs, ascending=False)
        print(stab.to_string(float_format=lambda x: f"{x:+.4f}"))


def auc_se(oos):
    """Hanley-McNeil approximate standard error for an AUC estimate."""
    y = oos["y"].values
    a = roc_auc_score(y, oos["prob"].values)
    n1, n0 = int(y.sum()), int((1 - y).sum())
    q1 = a / (2 - a)
    q2 = 2 * a**2 / (1 + a)
    var = (a * (1 - a) + (n1 - 1) * (q1 - a**2) + (n0 - 1) * (q2 - a**2)) / (n1 * n0)
    return float(np.sqrt(var))


# --------------------------------------------------------------------------
# Paired comparison between two variants
# --------------------------------------------------------------------------

def compare(result_a, result_b, labels=("A", "B"), n_boot=2000, seed=0):
    """Paired comparison on the games both variants predicted.

    Pairing matters: the same games are hard or easy for both models, so the
    *difference* is much less noisy than either estimate alone. A change can be
    real at 0.005 even though each AUC has an SE of 0.007.
    """
    merged = result_a.oos.merge(
        result_b.oos[["game_id", "prob"]], on="game_id", suffixes=("_a", "_b")
    )
    y = merged["y"].values
    pa, pb = merged["prob_a"].values, merged["prob_b"].values

    auc_a, auc_b = roc_auc_score(y, pa), roc_auc_score(y, pb)
    ll_a, ll_b = log_loss(y, pa), log_loss(y, pb)

    rng = np.random.default_rng(seed)
    idx = np.arange(len(y))
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        s = rng.choice(idx, size=len(idx), replace=True)
        if y[s].min() == y[s].max():      # degenerate resample
            diffs[i] = np.nan
            continue
        diffs[i] = roc_auc_score(y[s], pb[s]) - roc_auc_score(y[s], pa[s])
    diffs = diffs[~np.isnan(diffs)]

    lo, hi = np.percentile(diffs, [2.5, 97.5])
    p_better = float((diffs > 0).mean())

    print(f"\n--- {labels[1]} vs {labels[0]} (paired, n={len(y)}) ---")
    print(f"  AUC       {auc_a:.4f} -> {auc_b:.4f}   diff {auc_b - auc_a:+.4f}")
    print(f"  Log loss  {ll_a:.4f} -> {ll_b:.4f}   diff {ll_b - ll_a:+.4f}"
          f"   ({'better' if ll_b < ll_a else 'worse'})")
    print(f"  95% CI on AUC diff: [{lo:+.4f}, {hi:+.4f}]")
    print(f"  P(improvement) = {p_better:.3f}")
    verdict = "real" if lo > 0 else ("harmful" if hi < 0 else "not distinguishable from noise")
    print(f"  Verdict: {verdict}")

    return {"auc_diff": auc_b - auc_a, "ci": (lo, hi), "p_better": p_better}


# --------------------------------------------------------------------------
# Calibration
# --------------------------------------------------------------------------

def calibration_table(result, bins=10):
    """Are the probabilities honest? Essential before comparing to market prices."""
    oos = result.oos.copy()
    oos["bucket"] = pd.qcut(oos["prob"], bins, duplicates="drop")
    tbl = oos.groupby("bucket", observed=True).agg(
        n=("y", "size"),
        mean_pred=("prob", "mean"),
        actual=("y", "mean"),
    )
    tbl["error"] = tbl["actual"] - tbl["mean_pred"]
    print("\n--- calibration ---")
    print(tbl.to_string(float_format=lambda x: f"{x:.4f}"))
    return tbl


# --------------------------------------------------------------------------

if __name__ == "__main__":
    from team_data_pipeline import get_training_data
    from pitcher_pipeline import get_full_training_data

    df = get_full_training_data(get_training_data())

    feature_cols = [c for c in df.columns if
                    "season" in c or "last10" in c or "bullpen_ip_last3" in c]

    print(f"Features ({len(feature_cols)}): {sorted(feature_cols)}")
    print("\nWalk-forward:")
    result = walk_forward(df, feature_cols)
    summarize(result)
    calibration_table(result)