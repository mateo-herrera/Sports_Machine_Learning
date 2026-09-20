"""
Pitcher and bullpen feature pipeline for the MLB win-probability model.

Changes from the previous version
---------------------------------
1. FIP AND K% REPLACE ERA AND K/9. ERA over ~60 innings is dominated by
   defense and sequencing luck, which is why its coefficient was unstable and
   half the size on the away side. FIP strips out everything except the three
   outcomes a pitcher controls alone (HR, BB, K), and stabilizes far faster.
   K/9 is contaminated by baserunners -- a pitcher who allows traffic faces
   more batters per inning and inflates the rate. K% (strikeouts per batter
   faced) is the clean version.

   This requires walks, HBP, home runs and batters faced from the boxscore.
   They are in the same `pitching` dict already being parsed, but the existing
   parquet cache does not have them, so the cache must be rebuilt once.

2. SHRINKAGE INSTEAD OF min_periods FOR RATE STATS. Requiring 6+ prior starts
   would drop every pitcher's first five outings, which in the earliest loaded
   season means most of April. Rate stats are instead shrunk toward league
   average, weighted by innings actually thrown -- same treatment the team
   pipeline gives run differential. A pitcher with two starts is mostly league
   average; one with fifteen is almost entirely himself.

3. min_periods ON BULLPEN WINDOWS. Bullpen usage is a count, not a rate, so
   shrinkage doesn't apply. A full window is required instead.

4. DOUBLEHEADER ORDERING. game_id is now a tiebreaker in every sort, so
   shift(1) can't pull the wrong prior appearance.

5. SEASON-AWARE BULLPEN. A bullpen is a roster unit that turns over between
   years, so its windows reset each season. Pitcher windows deliberately do
   NOT reset -- it is the same individual, and September starts are legitimate
   evidence about April.

6. PITCHER DAYS REST, distinct from (and more useful than) team days rest.

7. CACHE VERSIONING, incremental saves, and vectorized team assignment.
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CACHE_PATH = os.path.join(SCRIPT_DIR, 'pitcher_starts.parquet')

# Bumped whenever the columns pulled from the boxscore change. A cache written
# by an older version is rebuilt rather than silently used with missing fields.
CACHE_VERSION = 2

RAW_COLS = [
    'game_id', 'is_home', 'pitcher_id', 'pitcher_name',
    'game_ip', 'game_er', 'game_k', 'game_bb', 'game_hbp', 'game_hr', 'game_bf',
    'bullpen_outs', 'bullpen_er', 'bullpen_ip', 'num_relievers',
]

# League-average anchors for the shrinkage priors. Fixed constants rather than
# values computed from the dataset, which would leak future information into
# past rows. Approximate modern MLB levels; exact values barely matter because
# features are standardized before fitting.
LEAGUE_FIP = 4.10
LEAGUE_K_PCT = 0.225
FIP_CONSTANT = 3.10

# Prior strength, in innings / batters faced. ~30 IP is about five starts.
PRIOR_IP = 30.0
PRIOR_BF = 120.0

PITCHER_STAT_COLS = [
    'fip_last10',
    'k_pct_last10',
    'pitcher_days_rest',
]

BULLPEN_STAT_COLS = [
    'bullpen_era_last5',
    'bullpen_ip_last3',
]

FEATURE_COLS = (
    [f'home_pitcher_{c}' for c in PITCHER_STAT_COLS]
    + [f'away_pitcher_{c}' for c in PITCHER_STAT_COLS]
    + [f'home_{c}' for c in BULLPEN_STAT_COLS]
    + [f'away_{c}' for c in BULLPEN_STAT_COLS]
)


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

def connect_player_endpoint(gamePk, timeout=15):
    url = f"https://statsapi.mlb.com/api/v1/game/{gamePk}/boxscore"
    response = requests.get(url, timeout=timeout)
    if response.status_code != 200:
        raise Exception(f"Error {response.status_code} fetching game {gamePk}")
    return response.json()


def get_starting_pitcher(team_data):
    """The pitcher credited with the start, including openers.

    Now also pulls BB, HBP, HR and batters faced, which FIP and K% need.
    """
    for _, player in team_data['players'].items():
        pitching = player.get('stats', {}).get('pitching', {})
        if pitching.get('gamesStarted') == 1:
            return {
                'pitcher_id': player['person']['id'],
                'pitcher_name': player['person']['fullName'],
                'game_ip': pitching.get('inningsPitched'),
                'game_er': pitching.get('earnedRuns', 0) or 0,
                'game_k': pitching.get('strikeOuts', 0) or 0,
                'game_bb': pitching.get('baseOnBalls', 0) or 0,
                'game_hbp': pitching.get('hitByPitch', 0) or 0,
                'game_hr': pitching.get('homeRuns', 0) or 0,
                'game_bf': pitching.get('battersFaced', 0) or 0,
            }
    return None


def get_bullpen_usage(team_data):
    """Innings and earned runs from every non-starting pitcher in one game."""
    total_outs = 0
    total_er = 0
    num_relievers = 0

    for _, player in team_data['players'].items():
        pitching = player.get('stats', {}).get('pitching', {})
        if not pitching or pitching.get('gamesStarted') == 1:
            continue
        if pitching.get('inningsPitched'):
            total_outs += ip_to_outs(pitching.get('inningsPitched'))
            total_er += pitching.get('earnedRuns', 0) or 0
            num_relievers += 1

    return {
        'bullpen_outs': total_outs,
        'bullpen_er': total_er,
        'bullpen_ip': total_outs / 3,
        'num_relievers': num_relievers,
    }


def get_starters_for_game(gamePK):
    data = connect_player_endpoint(gamePk=gamePK)
    return (
        get_starting_pitcher(data['teams']['home']),
        get_starting_pitcher(data['teams']['away']),
        get_bullpen_usage(data['teams']['home']),
        get_bullpen_usage(data['teams']['away']),
    )


def _load_cache(cache_path):
    """Read the cache, discarding it if it predates the current column set."""
    if not os.path.exists(cache_path):
        return pd.DataFrame()

    df = pd.read_parquet(cache_path)
    missing = [c for c in RAW_COLS if c not in df.columns]
    if missing:
        print(
            f"Cache at {cache_path} is missing {missing} (pre-v{CACHE_VERSION} "
            f"format). Rebuilding from scratch -- this will re-pull every game."
        )
        return pd.DataFrame()
    return df


def pull_all_pitcher_starts(gamePKs, cache_path=DEFAULT_CACHE_PATH,
                            workers=8, save_every=500):
    """Fetch boxscores for any games not already cached.

    Threaded: 8 workers is polite for an unauthenticated public endpoint.
    Drop to 4 if failures start appearing. Results arrive out of order, which
    is fine -- every downstream step sorts explicitly before computing.
    """
    existing_df = _load_cache(cache_path)
    already_pulled = set(existing_df['game_id'].unique()) if len(existing_df) else set()
    new_game_ids = [g for g in gamePKs if g not in already_pulled]
    print(f"{len(already_pulled)} games cached, {len(new_game_ids)} to pull")
    if not new_game_ids:
        return existing_df

    pitcher_rows, failures = [], 0

    def fetch(gamePK):
        home_sp, away_sp, home_pen, away_pen = get_starters_for_game(gamePK)
        out = []
        if home_sp:
            out.append({'game_id': gamePK, 'is_home': True, **home_sp, **home_pen})
        if away_sp:
            out.append({'game_id': gamePK, 'is_home': False, **away_sp, **away_pen})
        return out

    def flush():
        if not pitcher_rows:
            return
        combined = pd.concat([existing_df, pd.DataFrame(pitcher_rows)], ignore_index=True)
        tmp = cache_path + '.tmp'
        combined.to_parquet(tmp)
        os.replace(tmp, cache_path)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fetch, g): g for g in new_game_ids}
        for i, fut in enumerate(as_completed(futures)):
            try:
                pitcher_rows.extend(fut.result())
            except Exception as e:
                failures += 1
                if failures <= 10:
                    print(f"Failed on game {futures[fut]}: {e}")
            if i and i % save_every == 0:
                flush()
                print(f"  {i}/{len(new_game_ids)} done ({failures} failures)")

    flush()
    print(f"Pulled {len(new_game_ids) - failures}/{len(new_game_ids)} games")
    return _load_cache(cache_path)


# --------------------------------------------------------------------------
# Feature construction
# --------------------------------------------------------------------------

def ip_to_outs(ip_str):
    """MLB writes innings as 5.2 meaning 5 innings and 2 outs, not 5.67."""
    if ip_str is None or (isinstance(ip_str, float) and np.isnan(ip_str)):
        return 0
    ip_str = str(ip_str)
    if '.' not in ip_str:
        return int(ip_str) * 3
    whole, frac = ip_str.split('.')
    return int(whole) * 3 + int(frac)


def add_pitcher_rolling_stats(pitcher_df, game_dates, windows=(3, 5, 10)):
    """Rolling starter rates, all shifted so a game never sees itself.

    Rate stats are shrunk toward league average by innings thrown, so a
    pitcher's first start produces a usable (if uninformative) value rather
    than a NaN or a wild one-game extrapolation.
    """
    pitcher_df = pitcher_df.copy()
    pitcher_df['outs'] = pitcher_df['game_ip'].apply(ip_to_outs)

    pitcher_df = pitcher_df.merge(game_dates, on='game_id')
    pitcher_df['season'] = pd.to_datetime(pitcher_df['date']).dt.year
    pitcher_df = pitcher_df.sort_values(
        ['pitcher_id', 'date', 'game_id']
    ).reset_index(drop=True)

    # Days since this pitcher's own last start -- not the team's last game.
    pitcher_df['pitcher_days_rest'] = (
        pitcher_df.groupby('pitcher_id')['date'].diff().dt.days
    )
    pitcher_df['pitcher_days_rest'] = (
        pitcher_df['pitcher_days_rest'].clip(lower=0, upper=10).fillna(5)
    )

    # FIP numerator for a single game. Summing this over a window and dividing
    # by innings is the correct way to aggregate; averaging per-game FIPs is not.
    pitcher_df['fip_num'] = (
        13 * pitcher_df['game_hr']
        + 3 * (pitcher_df['game_bb'] + pitcher_df['game_hbp'])
        - 2 * pitcher_df['game_k']
    )

    g = pitcher_df.groupby('pitcher_id')

    def roll_sum(col, window):
        # fillna(0) matters: on a pitcher's first appearance the shifted window
        # is entirely NaN, so the sum is NaN and the shrinkage blend below
        # would produce NaN instead of falling back to the league-average
        # prior. An empty window genuinely has a sum of zero.
        return g[col].transform(
            lambda s: s.shift(1).rolling(window, min_periods=1).sum()
        ).fillna(0.0)

    for window in windows:
        outs = roll_sum('outs', window)
        ip = outs / 3
        er = roll_sum('game_er', window)
        k = roll_sum('game_k', window)
        bf = roll_sum('game_bf', window)
        fip_num = roll_sum('fip_num', window)

        # Raw ERA / K9 retained so the old and new features can be compared.
        pitcher_df[f'era_last{window}'] = (er / ip.replace(0, np.nan)) * 9
        pitcher_df[f'k_per9_last{window}'] = (k / ip.replace(0, np.nan)) * 9

        # Shrunk toward league average, weighted by sample size.
        pitcher_df[f'fip_last{window}'] = (
            (fip_num + PRIOR_IP * (LEAGUE_FIP - FIP_CONSTANT)) / (ip + PRIOR_IP)
        ) + FIP_CONSTANT
        pitcher_df[f'k_pct_last{window}'] = (
            (k + PRIOR_BF * LEAGUE_K_PCT) / (bf + PRIOR_BF)
        )

    return pitcher_df


def add_bullpen_rolling_stats(pitcher_df, final_df, windows=(3, 5)):
    """Rolling bullpen workload and quality, per team, reset each season."""
    pitcher_df = pitcher_df.copy()

    team_lookup = final_df[['game_id', 'home_team_id', 'away_team_id']].drop_duplicates()
    pitcher_df = pitcher_df.merge(team_lookup, on='game_id')
    pitcher_df['team_id'] = np.where(
        pitcher_df['is_home'], pitcher_df['home_team_id'], pitcher_df['away_team_id']
    )

    pitcher_df = pitcher_df.sort_values(
        ['team_id', 'season', 'date', 'game_id']
    ).reset_index(drop=True)

    g = pitcher_df.groupby(['team_id', 'season'])

    for window in windows:
        # Workload is a count: require a full window rather than shrinking.
        roll_ip = g['bullpen_ip'].transform(
            lambda s: s.shift(1).rolling(window, min_periods=window).sum()
        )
        roll_er = g['bullpen_er'].transform(
            lambda s: s.shift(1).rolling(window, min_periods=window).sum()
        )
        pitcher_df[f'bullpen_ip_last{window}'] = roll_ip
        pitcher_df[f'bullpen_era_last{window}'] = (
            roll_er / roll_ip.replace(0, np.nan)
        ) * 9

    return pitcher_df


# --------------------------------------------------------------------------
# Merging back to game level
# --------------------------------------------------------------------------

def _split_merge(final_df, pitcher_df, cols, prefix):
    """Attach a team's columns to the game row as home_* and away_*."""
    keep = ['game_id'] + cols
    home = pitcher_df.loc[pitcher_df['is_home'], keep].copy()
    away = pitcher_df.loc[~pitcher_df['is_home'], keep].copy()

    home = home.rename(columns={c: f'home_{prefix}{c}' for c in cols})
    away = away.rename(columns={c: f'away_{prefix}{c}' for c in cols})

    merged = final_df.merge(home, on='game_id', how='left')
    merged = merged.merge(away, on='game_id', how='left')
    return merged


def merge_pitcher_stats_to_games(final_df, pitcher_df):
    stat_cols = [c for c in pitcher_df.columns if c.startswith((
        'era_last', 'k_per9_last', 'fip_last', 'k_pct_last'
    ))] + ['pitcher_id', 'pitcher_name', 'pitcher_days_rest']
    return _split_merge(final_df, pitcher_df, stat_cols, prefix='pitcher_')


def merge_bullpen_stats_to_games(final_df, pitcher_df):
    stat_cols = [c for c in pitcher_df.columns
                 if c.startswith(('bullpen_ip_last', 'bullpen_era_last'))]
    return _split_merge(final_df, pitcher_df, stat_cols, prefix='')


def get_full_training_data(final_df, dropna=True):
    game_ids = final_df['game_id'].unique()
    pitcher_df = pull_all_pitcher_starts(game_ids)

    game_dates = final_df[['game_id', 'date']].drop_duplicates()
    pitcher_df = add_pitcher_rolling_stats(pitcher_df, game_dates)
    pitcher_df = add_bullpen_rolling_stats(pitcher_df, final_df)

    out = merge_pitcher_stats_to_games(final_df, pitcher_df)
    out = merge_bullpen_stats_to_games(out, pitcher_df)

    # Report coverage BEFORE dropping, so missing data is visible rather than
    # silently disappearing into a dropna the caller never sees.
    present = [c for c in FEATURE_COLS if c in out.columns]
    nan_counts = out[present].isna().sum()
    if nan_counts.any():
        print("NaN counts after pitcher/bullpen merge:")
        print(nan_counts[nan_counts > 0].to_string())

    if dropna:
        before = len(out)
        out = out.dropna(subset=present)
        print(f"Dropped {before - len(out)} of {before} games missing pitcher "
              f"features ({100 * (before - len(out)) / max(before, 1):.1f}%)")

    return out.sort_values(['date', 'game_id']).reset_index(drop=True)


if __name__ == '__main__':
    from team_data_pipeline import get_training_data

    df = get_full_training_data(get_training_data())
    print(f"\n{len(df)} games")
    print(df[[c for c in FEATURE_COLS if c in df.columns]].describe().T.to_string())


# --------------------------------------------------------------------------
# Serving support
# --------------------------------------------------------------------------

def append_upcoming_starts(pitcher_df, upcoming):
    """Append placeholder rows for tonight's probable starters.

    Same principle as the team side: rather than recomputing FIP, K% and the
    bullpen windows a second time in the prediction path, the upcoming games
    are appended and the SAME rolling code runs over everything. Counting
    stats are zero because a shift(1) window never reads the row's own values.

    Games whose probable pitcher is not yet announced are skipped.
    """
    rows = []
    for g in upcoming:
        for side, is_home in (('home', True), ('away', False)):
            pid = g.get(f'{side}_pitcher_id')
            if pid is None:
                continue
            rows.append({
                'game_id': g['game_id'],
                'is_home': is_home,
                'pitcher_id': pid,
                'pitcher_name': g.get(f'{side}_pitcher_name'),
                'game_ip': '0.0',
                'game_er': 0, 'game_k': 0, 'game_bb': 0,
                'game_hbp': 0, 'game_hr': 0, 'game_bf': 0,
                'bullpen_outs': 0, 'bullpen_er': 0,
                'bullpen_ip': 0.0, 'num_relievers': 0,
            })

    if not rows:
        return pitcher_df, set()

    placeholder = pd.DataFrame(rows)
    combined = pd.concat([pitcher_df, placeholder], ignore_index=True)
    return combined, {r['game_id'] for r in rows}


def build_upcoming_pitcher_features(pitcher_df, final_df, upcoming):
    """Pitcher and bullpen features for games that have not been played.

    final_df must already contain the upcoming games (game_id, date,
    home_team_id, away_team_id) so the bullpen windows can resolve teams.
    """
    combined, touched = append_upcoming_starts(pitcher_df, upcoming)
    if not touched:
        return pd.DataFrame()

    game_dates = final_df[['game_id', 'date']].drop_duplicates()
    combined = add_pitcher_rolling_stats(combined, game_dates)
    combined = add_bullpen_rolling_stats(combined, final_df)

    return combined[combined['game_id'].isin(touched)]