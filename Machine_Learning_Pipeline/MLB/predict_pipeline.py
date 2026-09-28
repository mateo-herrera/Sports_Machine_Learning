"""
Serve predictions for upcoming MLB games, alongside live Polymarket odds.

Why this was rewritten
----------------------
The previous version reimplemented every feature by hand (get_latest_team_stats,
get_latest_pitcher_stats, get_latest_bullpen_stats). That is the classic
train/serve skew bug: two copies of the same formulas that drift apart. By the
time the model moved to Elo, FIP, K% and difference features, the prediction
path was still producing season-long ERA and raw win percentage -- five of the
six features the model wanted did not exist, and because missing features were
handled with `continue`, the endpoint silently returned zero games.

This version computes NOTHING by hand. Upcoming games are appended to the
historical frame as placeholder rows with unknown outcomes, and the SAME
training pipeline runs over the whole thing. Every feature is shift(1)-based,
so a placeholder receives exactly the pre-game values it would have had if the
game were already played. Change a feature in the pipeline and this path
follows automatically.

Dates are processed one at a time: two unplayed games for the same team in one
frame would put a NaN inside the second one's rolling window.
"""

import json
import os
from datetime import date, datetime, timedelta

import joblib
import pandas as pd
import pytz
import requests

from .pitcher_pipeline import (
    BULLPEN_STAT_COLS,
    PITCHER_STAT_COLS,
    build_upcoming_pitcher_features,
    pull_all_pitcher_starts,
)
from .team_data_pipeline import (
    build_upcoming_team_features,
    clean_json_data,
    get_training_data,
    to_differences,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_DIR, 'mlb_model.joblib')

MIN_YEAR = 2022          # must match train_model.MIN_YEAR

TEAM_SHORT_NAMES = {
    108: "Angels", 109: "Diamondbacks", 110: "Orioles", 111: "Red Sox",
    112: "Cubs", 113: "Reds", 114: "Guardians", 115: "Rockies",
    116: "Tigers", 117: "Astros", 118: "Royals", 119: "Dodgers",
    120: "Nationals", 121: "Mets", 133: "Athletics", 134: "Pirates",
    135: "Padres", 136: "Mariners", 137: "Giants", 138: "Cardinals",
    139: "Rays", 140: "Rangers", 141: "Blue Jays", 142: "Twins",
    143: "Phillies", 144: "Braves", 145: "White Sox", 146: "Marlins",
    147: "Yankees", 158: "Brewers",
}


# --------------------------------------------------------------------------
# Schedule
# --------------------------------------------------------------------------

def get_upcoming_games():
    """Today's and tomorrow's schedule with probable starters.

    probablePitcher is the only source available before a game -- the
    boxscore used for training does not exist yet. Starters are sometimes
    scratched, so refresh close to first pitch rather than once a morning.
    """
    combined = []
    for offset in (0, 1):
        target = (date.today() + timedelta(days=offset)).strftime('%Y-%m-%d')
        url = (f"https://statsapi.mlb.com/api/v1/schedule?sportId=1"
               f"&date={target}&hydrate=probablePitcher")
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            raise Exception(f"Error {response.status_code} fetching schedule for {target}")
        combined.extend(response.json().get('dates', []))
    return {'dates': combined}


def extract_upcoming_game_info(data):
    games = []
    for date_entry in data['dates']:
        for game in date_entry['games']:
            t = game['teams']
            hp, ap = t['home'].get('probablePitcher'), t['away'].get('probablePitcher')
            games.append({
                'game_id': game['gamePk'],
                'date': date_entry['date'],
                'home_team_id': t['home']['team']['id'],
                'home_team_name': t['home']['team']['name'],
                'away_team_id': t['away']['team']['id'],
                'away_team_name': t['away']['team']['name'],
                'home_pitcher_id': hp['id'] if hp else None,
                'home_pitcher_name': hp['fullName'] if hp else None,
                'away_pitcher_id': ap['id'] if ap else None,
                'away_pitcher_name': ap['fullName'] if ap else None,
            })
    return games


# --------------------------------------------------------------------------
# Features, via the training pipeline
# --------------------------------------------------------------------------

def build_feature_frame(games, long_df, pitcher_df, hist_final_df):
    """One feature row per upcoming game, built by the training code itself."""
    frames = []

    for target_date in sorted({g['date'] for g in games}):
        todays = [g for g in games if g['date'] == target_date]

        team_rows = build_upcoming_team_features(long_df, todays)
        if team_rows.empty:
            continue

        # The bullpen windows need team ids for the upcoming games too.
        upcoming_lookup = pd.DataFrame([{
            'game_id': g['game_id'],
            'date': pd.to_datetime(g['date']),
            'home_team_id': g['home_team_id'],
            'away_team_id': g['away_team_id'],
        } for g in todays])
        lookup = pd.concat(
            [hist_final_df[['game_id', 'date', 'home_team_id', 'away_team_id']],
             upcoming_lookup],
            ignore_index=True,
        ).drop_duplicates(subset='game_id')

        pitch_rows = build_upcoming_pitcher_features(pitcher_df, lookup, todays)
        if pitch_rows.empty:
            continue

        merged = _attach_pitcher_columns(team_rows, pitch_rows)
        frames.append(merged)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _attach_pitcher_columns(team_rows, pitch_rows):
    """Split pitcher rows into home_/away_ columns, same naming as training."""
    p_cols = [c for c in PITCHER_STAT_COLS if c in pitch_rows.columns]
    b_cols = [c for c in BULLPEN_STAT_COLS if c in pitch_rows.columns]

    home = pitch_rows.loc[pitch_rows['is_home'], ['game_id'] + p_cols + b_cols].rename(
        columns={**{c: f'home_pitcher_{c}' for c in p_cols},
                 **{c: f'home_{c}' for c in b_cols}})
    away = pitch_rows.loc[~pitch_rows['is_home'], ['game_id'] + p_cols + b_cols].rename(
        columns={**{c: f'away_pitcher_{c}' for c in p_cols},
                 **{c: f'away_{c}' for c in b_cols}})

    out = team_rows.merge(home, on='game_id', how='left')
    return out.merge(away, on='game_id', how='left')



def format_game_time(game_date_str):
    utc = datetime.fromisoformat(game_date_str.replace('Z', '+00:00'))
    return utc.astimezone(pytz.timezone('America/New_York')).strftime('%-I:%M%p').lower()




# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def compute_predictions():
    saved = joblib.load(MODEL_PATH)
    model, trained_cols = saved['model'], saved['feature_cols']
    uses_differences = saved.get('uses_differences', False)
    metrics = saved.get('metrics', {})

    schedule = get_upcoming_games()            # once
    games = extract_upcoming_game_info(schedule)
    raw_lookup = {g['gamePk']: g for d in schedule['dates'] for g in d['games']}

    if not games:
        return {'games': {}, 'model_accuracy': metrics.get('accuracy')}

    long_df = clean_json_data(min_year=MIN_YEAR)
    hist_final_df = get_training_data(min_year=MIN_YEAR)
    pitcher_df = pull_all_pitcher_starts(hist_final_df['game_id'].unique())

    frame = build_feature_frame(games, long_df, pitcher_df, hist_final_df)
    if uses_differences:
        frame, _ = to_differences(frame, [c for c in frame.columns
                                          if c.startswith(('home_', 'away_'))])

    missing = [c for c in trained_cols if c not in frame.columns]
    if missing:
        raise KeyError(f"Feature mismatch: {missing}. Retrain, or check MIN_YEAR={MIN_YEAR}.")

    usable = frame.dropna(subset=trained_cols)
    prob_by_game = {}
    if not usable.empty:
        probs = model.predict_proba(usable[trained_cols])[:, 1]
        prob_by_game = dict(zip(usable['game_id'], probs))

    out = {}
    for g in games:
        raw = raw_lookup.get(g['game_id'], {})
        out[g['game_id']] = {
            'game_id': g['game_id'],
            'away': TEAM_SHORT_NAMES.get(g['away_team_id'], g['away_team_name']),
            'home': TEAM_SHORT_NAMES.get(g['home_team_id'], g['home_team_name']),
            'away_team_id': g['away_team_id'],
            'home_team_id': g['home_team_id'],
            'away_team_name': g['away_team_name'],
            'home_team_name': g['home_team_name'],
            'home_prediction': prob_by_game.get(g['game_id']),   # float or None
            'time': format_game_time(raw['gameDate']) if raw else None,
            'date': g['date'],
        }

    return {'games': out, 'model_accuracy': metrics.get('accuracy')}


