import requests
from datetime import date, timedelta, datetime, timezone
import pandas as pd
import joblib
import pytz
import json

from .team_data_pipeline import clean_json_data, get_training_data
from .pitcher_pipeline import get_full_training_data, pull_all_pitcher_starts, add_pitcher_rolling_stats
from .PolyMarket.polymarket_API import get_MLB_markets


import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_DIR, 'mlb_model.joblib')

#Hardcoded teams ids to shorter names
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


def get_upcoming_games():
    today_str = date.today().strftime('%Y-%m-%d')
    tomorrow_str = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')

    combined_dates = []

    for target_date in [today_str, tomorrow_str]:
        url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={target_date}&hydrate=probablePitcher"
        response = requests.get(url)

        if response.status_code != 200:
            raise Exception(f"Error {response.status_code} fetching schedule for {target_date}")

        data = response.json()
        combined_dates.extend(data.get('dates', []))

    return {'dates': combined_dates}

def extract_upcoming_game_info(data):
    games = []
    for date_entry in data['dates']:
        for game in date_entry['games']:
            t = game['teams']
            home_pitcher = t['home'].get('probablePitcher')
            away_pitcher = t['away'].get('probablePitcher')

            games.append({
                'game_id': game['gamePk'],
                'date': date_entry['date'],
                'home_team_id': t['home']['team']['id'],
                'home_team_name': t['home']['team']['name'],
                'away_team_id': t['away']['team']['id'],
                'away_team_name': t['away']['team']['name'],
                'home_pitcher_id': home_pitcher['id'] if home_pitcher else None,
                'home_pitcher_name': home_pitcher['fullName'] if home_pitcher else None,
                'away_pitcher_id': away_pitcher['id'] if away_pitcher else None,
                'away_pitcher_name': away_pitcher['fullName'] if away_pitcher else None,
            })
    return games

def get_latest_team_stats(long_df, team_id, windows=(5, 10, 20)):
    team_games = long_df[long_df['team_id'] == team_id].sort_values('date')
    if team_games.empty:
        return None

    stats = {}
    for window in windows:
        recent = team_games.tail(window)
        stats[f'win_pct_last{window}'] = recent['win'].mean()
        stats[f'run_diff_last{window}'] = recent['run_diff'].mean()

    stats['win_pct_season'] = team_games['win'].mean()
    stats['run_diff_season'] = team_games['run_diff'].mean()
    return stats


def get_latest_pitcher_stats(pitcher_df, pitcher_id, windows=(3, 5, 10)):
    pitcher_games = pitcher_df[pitcher_df['pitcher_id'] == pitcher_id].sort_values('date')
    if pitcher_games.empty:
        return None

    stats = {}
    for window in windows:
        recent = pitcher_games.tail(window)
        total_outs = recent['outs'].sum()
        total_er = recent['game_er'].sum()
        total_k = recent['game_k'].sum()
        stats[f'era_last{window}'] = (total_er / (total_outs / 3)) * 9 if total_outs > 0 else None
        stats[f'k_per9_last{window}'] = (total_k / (total_outs / 3)) * 9 if total_outs > 0 else None

    # season-long
    total_outs = pitcher_games['outs'].sum()
    total_er = pitcher_games['game_er'].sum()
    total_k = pitcher_games['game_k'].sum()
    stats['era_season'] = (total_er / (total_outs / 3)) * 9 if total_outs > 0 else None
    stats['k_per9_season'] = (total_k / (total_outs / 3)) * 9 if total_outs > 0 else None

    return stats

def get_latest_bullpen_stats(pitcher_df, team_id, windows=(3, 5)):
    team_bullpen = pitcher_df[pitcher_df['team_id'] == team_id].sort_values('date')
    if team_bullpen.empty:
        return None

    stats = {}
    for window in windows:
        recent = team_bullpen.tail(window)
        stats[f'bullpen_ip_last{window}'] = recent['bullpen_ip'].sum()
        total_er = recent['bullpen_er'].sum()
        total_ip = recent['bullpen_ip'].sum()
        stats[f'bullpen_era_last{window}'] = (total_er / total_ip) * 9 if total_ip > 0 else None

    return stats

def build_prediction_row(game, long_df, pitcher_df):
    home_team_stats = get_latest_team_stats(long_df, game['home_team_id'])
    away_team_stats = get_latest_team_stats(long_df, game['away_team_id'])

    home_pitcher_stats = get_latest_pitcher_stats(pitcher_df, game['home_pitcher_id']) if game['home_pitcher_id'] else None
    away_pitcher_stats = get_latest_pitcher_stats(pitcher_df, game['away_pitcher_id']) if game['away_pitcher_id'] else None

    home_bullpen_stats = get_latest_bullpen_stats(pitcher_df, game['home_team_id'])
    away_bullpen_stats = get_latest_bullpen_stats(pitcher_df, game['away_team_id'])

    row = {'game_id': game['game_id'], 'home_team_name': game['home_team_name'], 'away_team_name': game['away_team_name']}

    if home_team_stats:
        row.update({f'home_{k}': v for k, v in home_team_stats.items()})
    if away_team_stats:
        row.update({f'away_{k}': v for k, v in away_team_stats.items()})
    if home_pitcher_stats:
        row.update({f'home_pitcher_{k}': v for k, v in home_pitcher_stats.items()})
    if away_pitcher_stats:
        row.update({f'away_pitcher_{k}': v for k, v in away_pitcher_stats.items()})
    if home_bullpen_stats:
        row.update({f'home_{k}': v for k, v in home_bullpen_stats.items()})
    if away_bullpen_stats:
        row.update({f'away_{k}': v for k, v in away_bullpen_stats.items()})

    return row


def format_game_time(game_date_str):
    """Convert '2026-09-16T17:10:00Z' to '1:05pm' Eastern."""
    utc_time = datetime.fromisoformat(game_date_str.replace('Z', '+00:00'))
    eastern = utc_time.astimezone(pytz.timezone('America/New_York'))
    return eastern.strftime('%-I:%M%p').lower()



def match_polymarket_to_game(market_games, home_team_full, away_team_full):
    for market in market_games:
        title = market.get("game_title", "")
        if home_team_full in title and away_team_full in title:
            return market
    return None


def parse_polymarket_odds(market, home_team_full, away_team_full):
    if not market:
        return None, None

    outcomes = market.get("outcomes")
    prices = market.get("outcomePrices")
    if not outcomes or not prices:
        return None, None

    if isinstance(outcomes, str):
        outcomes = json.loads(outcomes)
    if isinstance(prices, str):
        prices = json.loads(prices)

    home_price, away_price = None, None
    for outcome, price in zip(outcomes, prices):
        if outcome == home_team_full:
            home_price = float(price)
        elif outcome == away_team_full:
            away_price = float(price)

    return home_price, away_price


def get_predictions_for_upcoming_games():
    saved = joblib.load(MODEL_PATH) 
    model_cv = saved['model']
    trained_feature_cols = saved['feature_cols']
    metrics = saved.get('metrics', {})

    raw_data = get_upcoming_games()
    games = extract_upcoming_game_info(raw_data)

    final_df = get_training_data()
    long_df = clean_json_data()
    long_df['run_diff'] = long_df['runs_scored'] - long_df['runs_allowed']

    game_ids = final_df['game_id'].unique()
    pitcher_df = pull_all_pitcher_starts(game_ids)
    game_dates = final_df[['game_id', 'date']].drop_duplicates()
    pitcher_df = add_pitcher_rolling_stats(pitcher_df, game_dates)
    team_lookup = final_df[['game_id', 'home_team_id', 'away_team_id']].drop_duplicates()
    pitcher_df = pitcher_df.merge(team_lookup, on='game_id')
    pitcher_df['team_id'] = pitcher_df.apply(lambda r: r['home_team_id'] if r['is_home'] else r['away_team_id'], axis=1)

    # need raw game times, so re-fetch the game dict by game_id from raw_data
    raw_game_lookup = {}
    for date_entry in raw_data['dates']:
        for g in date_entry['games']:
            raw_game_lookup[g['gamePk']] = g

    market_games = get_MLB_markets()  # fetch once, reused for every game below

    results = []
    for game in games:
        row = build_prediction_row(game, long_df, pitcher_df)
        missing = [c for c in trained_feature_cols if c not in row or row[c] is None]
        if missing:
            continue  # skip games without enough data yet

        X_pred = pd.DataFrame([{c: row[c] for c in trained_feature_cols}])
        prob_home_win = model_cv.predict_proba(X_pred)[0, 1]
        prob_away_win = 1 - prob_home_win

        raw_game = raw_game_lookup[game['game_id']]

        # match this game to polymarket using FULL team names
        polymarket_match = match_polymarket_to_game(market_games, game['home_team_name'], game['away_team_name'])
        home_odds, away_odds = parse_polymarket_odds(polymarket_match, game['home_team_name'], game['away_team_name'])

        results.append({
            'game_id': game['game_id'],
            'away': TEAM_SHORT_NAMES.get(game['away_team_id'], game['away_team_name']),
            'home': TEAM_SHORT_NAMES.get(game['home_team_id'], game['home_team_name']),
            'home_prediction': f"{prob_home_win:.0%}",
            'away_prediction': f"{prob_away_win:.0%}",
            'home_polymarket': f"{home_odds:.0%}" if home_odds is not None else None,
            'away_polymarket': f"{away_odds:.0%}" if away_odds is not None else None,
            'time': format_game_time(raw_game['gameDate']),
            'date': game['date'],
        })

    return {
        'games': results,
        'model_accuracy': metrics.get('accuracy')
    }
