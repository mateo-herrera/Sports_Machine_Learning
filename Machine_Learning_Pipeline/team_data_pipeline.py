"""
Team-level feature pipeline for the MLB win-probability model.

Changes from the previous version
---------------------------------
1. SEASON-AWARE GROUPING. Rolling and expanding stats used to group by
   team_id alone, so a 2026 game's "season" run differential was really a
   four-year franchise average spanning three different rosters. Everything
   now groups by (team_id, season).

2. min_periods=window. Previously min_periods=1 meant a team's second game of
   the year got a "last 10" figure computed from one game. Those rows produced
   values rather than NaN, so dropna never caught them -- roughly 10-15% of the
   training set was near-random noise.

3. DOUBLEHEADER ORDERING. sort_values(['team_id','date']) is not stable across
   two games sharing a date, so shift(1) could pull the wrong prior game.
   game_id is now a tiebreaker everywhere.

4. PRIOR-SEASON RUN DIFFERENTIAL, plus a shrinkage blend. Requiring a full
   season-to-date sample would throw away April. Instead, season-to-date run
   differential is shrunk toward the team's prior-season figure, weighted by
   how many games have actually been played. On opening day the estimate IS
   last year's team; by August the prior is irrelevant. This is a standard
   empirical-Bayes treatment and it fixes the cold-start without dropping rows.

5. Removed the duplicated clean_json_data() call in get_training_data().

Note on feature selection
-------------------------
Use the explicit FEATURE_COLS list below, not a substring filter. This module
now creates a literal `season` column holding the year, which a filter like
`'season' in c` would happily pick up and feed to the model as a feature.
"""

import glob
import json
import math
import os

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Shrinkage strength for the season-to-date blend, in games. At K=30 a team's
# estimate is half prior-season / half current once it has played 30 games.
PRIOR_WEIGHT = 30

# --- Elo parameters ---------------------------------------------------------
# K is much lower than in chess or football because one baseball game carries
# very little information about team quality. These are FiveThirtyEight's MLB
# values and are a sane starting point; K is the one worth tuning.
ELO_START = 1500.0
ELO_K = 4.0             # update size per game
ELO_HFA = 24.0          # home-field advantage, in rating points
ELO_REGRESS = 0.25      # fraction pulled back toward 1500 each offseason
ELO_USE_MOV = True      # scale updates by margin of victory

# The features actually fed to the model. Explicit, so a rename fails loudly
# instead of silently shrinking the feature set.
TEAM_STAT_COLS = [
    'elo',                     # opponent-adjusted team strength
    'run_diff_blended',        # season-to-date, shrunk toward prior season
    'run_diff_last10',         # recent form
    'win_pct_last10',
    'prior_season_run_diff',   # stable talent prior, available on opening day
    'days_rest',
]

FEATURE_COLS = (
    [f'home_{c}' for c in TEAM_STAT_COLS]
    + [f'away_{c}' for c in TEAM_STAT_COLS]
)


def open_json(filepath):
    with open(filepath, 'r') as file:
        return json.load(file)


def clean_json_data(min_year=2023):
    """Parse schedule JSON into one row per team per game."""
    filepaths = sorted(glob.glob(os.path.join(SCRIPT_DIR, 'Schedule', 'Schedule_output_*.json')))
    filepaths = [f for f in filepaths if int(f.split('_')[-1].split('.')[0]) >= min_year]
    print(f"Loading {len(filepaths)} season files")

    games = []
    skipped = 0
    for filepath in filepaths:
        data = open_json(filepath)
        for date_entry in data['dates']:
            for game in date_entry['games']:
                if game['status']['detailedState'] != 'Final':
                    continue
                t = game['teams']

                if 'isWinner' not in t['home'] or 'isWinner' not in t['away']:
                    skipped += 1
                    continue

                for side, other, is_home in (('home', 'away', True), ('away', 'home', False)):
                    games.append({
                        'date': date_entry['date'],
                        'game_id': game['gamePk'],
                        'team_id': t[side]['team']['id'],
                        'team_name': t[side]['team']['name'],
                        'opponent_id': t[other]['team']['id'],
                        'opponent_name': t[other]['team']['name'],
                        'runs_scored': t[side]['score'],
                        'runs_allowed': t[other]['score'],
                        'win': int(t[side]['isWinner']),
                        'is_home': is_home,
                    })

    print(f"Skipped {skipped} games missing isWinner")

    long_df = pd.DataFrame(games)
    long_df['date'] = pd.to_datetime(long_df['date'])
    long_df['season'] = long_df['date'].dt.year
    long_df = long_df.drop_duplicates(subset=['game_id', 'team_id'])

    # game_id breaks ties within a date so doubleheaders order correctly.
    long_df = long_df.sort_values(['team_id', 'date', 'game_id']).reset_index(drop=True)
    return long_df


def add_elo_ratings(long_df, k=ELO_K, hfa=ELO_HFA, regress=ELO_REGRESS,
                    use_mov=ELO_USE_MOV, start=ELO_START):
    """Opponent-adjusted team strength, updated after every game.

    Why this exists: run_diff_blended treats +1.2 against the league's worst
    teams the same as +1.2 against its best. Early in a season, when schedules
    are badly unbalanced, that is a large distortion sitting on the model's
    strongest feature.

    Elo fixes it structurally. The update is proportional to how surprising
    the result was, so beating a weak team barely moves you and losing to one
    costs a lot. Strength of schedule is handled with no separate calculation.

    Strictly forward-looking by construction: the rating attached to a game is
    the one that existed before it was played. There is no window to get wrong
    and no shift(1) to forget.

    Adds two columns per team-row:
      elo      -- this team's rating going into the game
      elo_exp  -- Elo's own win probability for this team in this game
    """
    long_df = long_df.sort_values(['date', 'game_id', 'is_home']).reset_index(drop=True)

    # One row per game, home side first.
    games = (
        long_df[long_df['is_home']]
        [['game_id', 'date', 'season', 'team_id', 'opponent_id', 'win',
          'runs_scored', 'runs_allowed']]
        .sort_values(['date', 'game_id'])
        .reset_index(drop=True)
    )

    ratings = {}
    last_season = None
    pre_home, pre_away, exp_home = [], [], []

    for row in games.itertuples(index=False):
        # Offseason: pull every team partway back toward the mean. Rosters
        # change, and last year's 100-win team is rarely this year's.
        if last_season is not None and row.season != last_season:
            for tid in ratings:
                ratings[tid] = start + (1 - regress) * (ratings[tid] - start)
        last_season = row.season

        h = ratings.setdefault(row.team_id, start)
        a = ratings.setdefault(row.opponent_id, start)

        e_home = 1.0 / (1.0 + 10 ** ((a - h - hfa) / 400.0))

        pre_home.append(h)
        pre_away.append(a)
        exp_home.append(e_home)

        # An unplayed game (appended for prediction) gets a pre-game rating
        # but must not update anything -- there is no result yet.
        if row.win is None or (isinstance(row.win, float) and math.isnan(row.win)):
            continue

        actual = 1.0 if row.win else 0.0
        shift = k * (actual - e_home)

        if use_mov:
            # A blowout is stronger evidence than a one-run game, but the
            # effect is damped logarithmically and scaled down when the
            # favorite wins, which prevents good teams running away.
            margin = abs(row.runs_scored - row.runs_allowed)
            elo_diff_winner = (h - a + hfa) if actual == 1.0 else (a - h - hfa)
            mult = math.log(margin + 1.0) * (2.2 / (elo_diff_winner * 0.001 + 2.2))
            shift *= mult

        ratings[row.team_id] = h + shift
        ratings[row.opponent_id] = a - shift

    games['home_elo_pre'] = pre_home
    games['away_elo_pre'] = pre_away
    games['home_elo_exp'] = exp_home

    # Map back onto the long (one row per team-game) frame.
    home_map = games[['game_id', 'home_elo_pre', 'home_elo_exp']].rename(
        columns={'home_elo_pre': 'elo', 'home_elo_exp': 'elo_exp'}
    )
    home_map['is_home'] = True

    away_map = games[['game_id', 'away_elo_pre', 'home_elo_exp']].copy()
    away_map['elo'] = away_map['away_elo_pre']
    away_map['elo_exp'] = 1.0 - away_map['home_elo_exp']
    away_map['is_home'] = False
    away_map = away_map[['game_id', 'elo', 'elo_exp', 'is_home']]

    elo_long = pd.concat([home_map[['game_id', 'elo', 'elo_exp', 'is_home']], away_map],
                         ignore_index=True)

    return long_df.merge(elo_long, on=['game_id', 'is_home'], how='left')


def add_prior_season_stats(long_df):
    """Each team's final run differential and win pct from the previous season.

    Available on opening day, unlike anything season-to-date. Teams with no
    prior season in the data (the earliest year loaded) get 0.0 -- i.e. treated
    as league average, which is the honest default when we know nothing.
    """
    season_totals = (
        long_df.groupby(['team_id', 'season'])
        .agg(final_run_diff=('run_diff', 'mean'), final_win_pct=('win', 'mean'))
        .reset_index()
    )
    season_totals['season'] = season_totals['season'] + 1   # shift forward one year
    season_totals = season_totals.rename(columns={
        'final_run_diff': 'prior_season_run_diff',
        'final_win_pct': 'prior_season_win_pct',
    })

    long_df = long_df.merge(season_totals, on=['team_id', 'season'], how='left')
    long_df['prior_season_run_diff'] = long_df['prior_season_run_diff'].fillna(0.0)
    long_df['prior_season_win_pct'] = long_df['prior_season_win_pct'].fillna(0.5)
    return long_df


def add_rolling_stats(long_df, windows=(10,)):
    """Rolling and season-to-date features, all strictly backward-looking.

    Every computation is shift(1) before the window, so the game being
    predicted never contributes to its own features.
    """
    long_df = long_df.sort_values(['team_id', 'season', 'date', 'game_id']).reset_index(drop=True)
    long_df['run_diff'] = long_df['runs_scored'] - long_df['runs_allowed']

    long_df = add_prior_season_stats(long_df)
    long_df = add_elo_ratings(long_df)
    long_df = long_df.sort_values(
        ['team_id', 'season', 'date', 'game_id']
    ).reset_index(drop=True)

    # Days since this team's last game, reset at season boundaries so an
    # opening-day game doesn't inherit a 180-day gap from last October.
    long_df['days_rest'] = (
        long_df.groupby(['team_id', 'season'])['date'].diff().dt.days
    )
    long_df['days_rest'] = long_df['days_rest'].clip(lower=0, upper=5).fillna(5)

    grouped = long_df.groupby(['team_id', 'season'])
    grouped_win = grouped['win']
    grouped_diff = grouped['run_diff']

    # --- rolling windows: require a FULL window, no partial samples ---
    for window in windows:
        long_df[f'win_pct_last{window}'] = grouped_win.transform(
            lambda s: s.shift(1).rolling(window, min_periods=window).mean()
        )
        long_df[f'run_diff_last{window}'] = grouped_diff.transform(
            lambda s: s.shift(1).rolling(window, min_periods=window).mean()
        )

    # --- season to date ---
    long_df['games_played'] = grouped_win.transform(
        lambda s: s.shift(1).expanding(min_periods=0).count()
    ).fillna(0)
    run_diff_sum = grouped_diff.transform(
        lambda s: s.shift(1).expanding(min_periods=0).sum()
    ).fillna(0.0)
    win_sum = grouped_win.transform(
        lambda s: s.shift(1).expanding(min_periods=0).sum()
    ).fillna(0.0)

    long_df['run_diff_season'] = (run_diff_sum / long_df['games_played']).where(
        long_df['games_played'] > 0
    )
    long_df['win_pct_season'] = (win_sum / long_df['games_played']).where(
        long_df['games_played'] > 0
    )

    # --- shrinkage blend: season-to-date pulled toward prior season ---
    n = long_df['games_played']
    long_df['run_diff_blended'] = (
        (run_diff_sum + PRIOR_WEIGHT * long_df['prior_season_run_diff'])
        / (n + PRIOR_WEIGHT)
    )
    long_df['win_pct_blended'] = (
        (win_sum + PRIOR_WEIGHT * long_df['prior_season_win_pct'])
        / (n + PRIOR_WEIGHT)
    )

    return long_df


def build_game_level_df(long_df, stat_cols=None):
    """Pivot from one row per team-game to one row per game."""
    stat_cols = list(stat_cols) if stat_cols is not None else list(TEAM_STAT_COLS)

    missing = [c for c in stat_cols if c not in long_df.columns]
    if missing:
        raise KeyError(f"Requested stat columns not in dataframe: {missing}")

    home_side = long_df[long_df['is_home']].copy()
    away_side = long_df[~long_df['is_home']].copy()

    home_side = home_side.rename(columns={c: f'home_{c}' for c in stat_cols})
    away_side = away_side.rename(columns={c: f'away_{c}' for c in stat_cols})

    final_df = home_side[
        ['game_id', 'date', 'season', 'team_id', 'win'] + [f'home_{c}' for c in stat_cols]
    ].merge(
        away_side[['game_id', 'team_id'] + [f'away_{c}' for c in stat_cols]],
        on='game_id',
        suffixes=('_home', '_away'),
    )

    final_df = final_df.rename(columns={
        'team_id_home': 'home_team_id',
        'team_id_away': 'away_team_id',
        'win': 'home_win',
    })

    feature_cols = [f'home_{c}' for c in stat_cols] + [f'away_{c}' for c in stat_cols]
    before = len(final_df)
    final_df = final_df.dropna(subset=feature_cols)
    print(f"Dropped {before - len(final_df)} of {before} games with incomplete features "
          f"({100 * (before - len(final_df)) / max(before, 1):.1f}%)")

    return final_df.sort_values(['date', 'game_id']).reset_index(drop=True)


def get_training_data(min_year=2023, stat_cols=None):
    """Single entry point -- everything else calls this."""
    long_df = clean_json_data(min_year=min_year)
    long_df = add_rolling_stats(long_df)
    return build_game_level_df(long_df, stat_cols=stat_cols)


if __name__ == '__main__':
    df = get_training_data()
    print(f"\n{len(df)} games, {df['season'].min()}-{df['season'].max()}")
    print(f"Home win rate: {df['home_win'].mean():.4f}")
    print(f"\nPer season:\n{df.groupby('season').size()}")
    print(f"\nFeatures ({len(FEATURE_COLS)}):")
    print(df[FEATURE_COLS].describe().T.to_string())


# --------------------------------------------------------------------------
# Serving support
# --------------------------------------------------------------------------

def append_upcoming_games(long_df, upcoming):
    """Append not-yet-played games as placeholder rows with unknown outcomes.

    This is what keeps training and serving consistent. Instead of
    reimplementing every rolling window, shrinkage blend and Elo update a
    second time in the prediction path -- which is how the two drift apart --
    the upcoming games are appended to the historical frame and the SAME
    add_rolling_stats() is run over the whole thing. Because every feature is
    shift(1)-based, a placeholder row receives exactly the pre-game values it
    would have received had the game already been played.

    `upcoming` is a list of dicts with game_id, date, home_team_id,
    away_team_id.

    Pass ONE date at a time. Two unplayed games for the same team in a single
    frame would put a NaN inside the second one's rolling window.
    """
    rows = []
    for g in upcoming:
        for side, other, is_home in (('home', 'away', True), ('away', 'home', False)):
            rows.append({
                'date': pd.to_datetime(g['date']),
                'game_id': g['game_id'],
                'team_id': g[f'{side}_team_id'],
                'team_name': g.get(f'{side}_team_name'),
                'opponent_id': g[f'{other}_team_id'],
                'opponent_name': g.get(f'{other}_team_name'),
                'runs_scored': float('nan'),
                'runs_allowed': float('nan'),
                'win': float('nan'),
                'is_home': is_home,
            })

    placeholder = pd.DataFrame(rows)
    placeholder['season'] = placeholder['date'].dt.year

    out = pd.concat([long_df, placeholder], ignore_index=True)
    return out.sort_values(['team_id', 'date', 'game_id']).reset_index(drop=True)


def build_upcoming_team_features(long_df, upcoming, stat_cols=None):
    """Team-level feature rows for games that have not been played yet."""
    stat_cols = list(stat_cols) if stat_cols is not None else list(TEAM_STAT_COLS)

    combined = append_upcoming_games(long_df, upcoming)
    combined = add_rolling_stats(combined)

    wanted = {g['game_id'] for g in upcoming}
    rows = combined[combined['game_id'].isin(wanted)]
    return build_game_level_df(rows, stat_cols=stat_cols)


def to_differences(df, feature_cols):
    """Collapse each home_X / away_X pair into a single X_diff column.

    Lives here rather than in the training script because BOTH training and
    serving must apply the identical transform. Two copies would drift.

    Sign convention: positive means the home side has more of the thing. For
    FIP, more is worse, so a positive diff favours the away team.

    Columns without a partner are carried through untouched rather than
    dropped -- silent feature loss is the failure mode that a substring
    filter caused earlier in this project.
    """
    stems, unpaired = [], []
    for c in feature_cols:
        if c.startswith('home_') and f'away_{c[len("home_"):]}' in feature_cols:
            stems.append(c[len('home_'):])
        elif c.startswith('away_') and f'home_{c[len("away_"):]}' in feature_cols:
            continue
        else:
            unpaired.append(c)

    out = df.copy()
    diff_cols = []
    for stem in stems:
        col = f'{stem}_diff'
        out[col] = out[f'home_{stem}'] - out[f'away_{stem}']
        diff_cols.append(col)

    return out, diff_cols + unpaired