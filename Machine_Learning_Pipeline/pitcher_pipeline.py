import requests
import os
import time
import pandas as pd

#Connects to API Endpoint
def connect_player_endpoint(gamePk):
    player_boxscores = f"https://statsapi.mlb.com/api/v1/game/{gamePk}/boxscore"
    response = requests.get(player_boxscores)

    if response.status_code != 200:
        raise Exception(f"Error {response.status_code} fetching game {gamePk}")

    return response.json()



#Gets the starting pitchers stats from json response 
def get_starting_pitcher(data):
    for player_id, player in data['players'].items():
        pitching = player.get('stats', {}).get('pitching', {})
        if pitching.get('gamesStarted') == 1:
            return {
                'pitcher_id': player['person']['id'],
                'pitcher_name': player['person']['fullName'],
                'game_ip': pitching.get('inningsPitched'),
                'game_er': pitching.get('earnedRuns'),
                'game_k': pitching.get('strikeOuts'),
            }
    return None

#Gets the starters from the game specified and the bullpen
def get_starters_for_game(gamePK):
    data = connect_player_endpoint(gamePk=gamePK)
    home_starter = get_starting_pitcher(data['teams']['home'])
    away_starter = get_starting_pitcher(data['teams']['away'])
    home_bullpen = get_bullpen_usage(data['teams']['home'])
    away_bullpen = get_bullpen_usage(data['teams']['away'])
    return home_starter, away_starter, home_bullpen, away_bullpen

#Path to save cache for getting all the starting pitchers from all the games
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CACHE_PATH = os.path.join(SCRIPT_DIR, 'pitcher_starts.parquet')


#Goes through all the games and find the starting pitcher for those games
def pull_all_pitcher_starts(gamePKs, cache_path=DEFAULT_CACHE_PATH):
    if os.path.exists(cache_path):
        existing_df = pd.read_parquet(cache_path)
        already_pulled = set(existing_df['game_id'].unique())
    else:
        existing_df = pd.DataFrame()
        already_pulled = set()

    new_game_ids = [g for g in gamePKs if g not in already_pulled]
    print(f"{len(already_pulled)} games already cached, {len(new_game_ids)} new games to pull")

    if not new_game_ids:
        return existing_df

    pitcher_rows = []
    for i, gamePK in enumerate(new_game_ids):
        try:
            home_starter, away_starter, home_bullpen, away_bullpen = get_starters_for_game(gamePK)
            if home_starter:
                pitcher_rows.append({'game_id': gamePK, 'is_home': True, **home_starter, **home_bullpen})
            if away_starter:
                pitcher_rows.append({'game_id': gamePK, 'is_home': False, **away_starter, **away_bullpen})
        except Exception as e:
            print(f"Failed on game {gamePK}: {e}")

        time.sleep(0.1)
        if i % 100 == 0:
            print(f"{i}/{len(new_game_ids)} done")

    new_df = pd.DataFrame(pitcher_rows)
    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    combined_df.to_parquet(cache_path)
    return combined_df

#Converts decimal to fractions for outs 
def ip_to_outs(ip_str):
    ip_str = str(ip_str)
    if '.' not in ip_str:
        return int(ip_str) * 3
    whole, frac = ip_str.split('.')
    return int(whole) * 3 + int(frac)

#adds pitcher stats
def add_pitcher_rolling_stats(pitcher_df, game_dates, windows=(3, 5, 10)):
    pitcher_df = pitcher_df.copy()
    pitcher_df['outs'] = pitcher_df['game_ip'].apply(ip_to_outs)

    pitcher_df = pitcher_df.merge(game_dates, on='game_id')
    pitcher_df = pitcher_df.sort_values(['pitcher_id', 'date']).reset_index(drop=True)

    grouped_er = pitcher_df.groupby('pitcher_id')['game_er']
    grouped_outs = pitcher_df.groupby('pitcher_id')['outs']
    grouped_k = pitcher_df.groupby('pitcher_id')['game_k']

    for window in windows:
        roll_er = grouped_er.transform(lambda s: s.shift(1).rolling(window, min_periods=1).sum())
        roll_outs = grouped_outs.transform(lambda s: s.shift(1).rolling(window, min_periods=1).sum())
        pitcher_df[f'era_last{window}'] = (roll_er / (roll_outs / 3)) * 9

        roll_k = grouped_k.transform(lambda s: s.shift(1).rolling(window, min_periods=1).sum())
        pitcher_df[f'k_per9_last{window}'] = (roll_k / (roll_outs / 3)) * 9

    return pitcher_df

#ADDS THE BULLPENS ROLLING STATS
def add_bullpen_rolling_stats(pitcher_df, final_df, windows=(3, 5)):
    pitcher_df = pitcher_df.copy()

    # attach team_id: home rows get home_team_id, away rows get away_team_id
    team_lookup = final_df[['game_id', 'home_team_id', 'away_team_id']].drop_duplicates()
    pitcher_df = pitcher_df.merge(team_lookup, on='game_id')
    pitcher_df['team_id'] = pitcher_df.apply(
        lambda row: row['home_team_id'] if row['is_home'] else row['away_team_id'], axis=1
    )

    pitcher_df = pitcher_df.sort_values(['team_id', 'date']).reset_index(drop=True)

    grouped_ip = pitcher_df.groupby('team_id')['bullpen_ip']
    grouped_er = pitcher_df.groupby('team_id')['bullpen_er']

    for window in windows:
        pitcher_df[f'bullpen_ip_last{window}'] = grouped_ip.transform(
            lambda s: s.shift(1).rolling(window, min_periods=1).sum()
        )
        roll_er = grouped_er.transform(lambda s: s.shift(1).rolling(window, min_periods=1).sum())
        roll_ip = grouped_ip.transform(lambda s: s.shift(1).rolling(window, min_periods=1).sum())
        pitcher_df[f'bullpen_era_last{window}'] = (roll_er / roll_ip.replace(0, pd.NA)) * 9

    return pitcher_df

#Merges bullpen stats
def merge_bullpen_stats_to_games(final_df, pitcher_df_with_bullpen):
    bullpen_cols = [c for c in pitcher_df_with_bullpen.columns if
                    c.startswith('bullpen_ip_last') or c.startswith('bullpen_era_last')]
    
    home_bullpen = pitcher_df_with_bullpen[pitcher_df_with_bullpen['is_home']][['game_id'] + bullpen_cols].copy()
    away_bullpen = pitcher_df_with_bullpen[~pitcher_df_with_bullpen['is_home']][['game_id'] + bullpen_cols].copy()

    home_bullpen = home_bullpen.rename(columns={c: f'home_{c}' for c in bullpen_cols})
    away_bullpen = away_bullpen.rename(columns={c: f'away_{c}' for c in bullpen_cols})

    merged = final_df.merge(home_bullpen, on='game_id', how='left')
    merged = merged.merge(away_bullpen, on='game_id', how='left')
    return merged

#merges the pitchers stats to the main df
def merge_pitcher_stats_to_games(final_df, pitcher_df):
    stat_cols = [c for c in pitcher_df.columns if
                 c.startswith('era_last') or c.startswith('k_per9_last')]

    home_pitchers = pitcher_df[pitcher_df['is_home']][['game_id', 'pitcher_id', 'pitcher_name'] + stat_cols].copy()
    away_pitchers = pitcher_df[~pitcher_df['is_home']][['game_id', 'pitcher_id', 'pitcher_name'] + stat_cols].copy()

    home_pitchers = home_pitchers.rename(columns={c: f'home_pitcher_{c}' for c in ['pitcher_id', 'pitcher_name'] + stat_cols})
    away_pitchers = away_pitchers.rename(columns={c: f'away_pitcher_{c}' for c in ['pitcher_id', 'pitcher_name'] + stat_cols})

    merged = final_df.merge(home_pitchers, on='game_id', how='left')
    merged = merged.merge(away_pitchers, on='game_id', how='left')
    return merged


def get_bullpen_usage(team_data):
    """Sum up innings pitched by all NON-starting pitchers for a team in one game."""
    total_outs = 0
    total_er = 0
    num_relievers = 0

    for player_id, player in team_data['players'].items():
        pitching = player.get('stats', {}).get('pitching', {})
        if not pitching:
            continue
        # skip the starter — we only want relief innings
        if pitching.get('gamesStarted') == 1:
            continue
        # this player pitched in relief this game
        if pitching.get('inningsPitched'):
            total_outs += ip_to_outs(pitching.get('inningsPitched'))
            total_er += pitching.get('earnedRuns', 0)
            num_relievers += 1

    return {
        'bullpen_outs': total_outs,
        'bullpen_er': total_er,
        'bullpen_ip': total_outs / 3,
        'num_relievers': num_relievers,
    }

#Ties everything up
def get_full_training_data(final_df):
    game_ids = final_df['game_id'].unique()
    pitcher_df = pull_all_pitcher_starts(game_ids)

    game_dates = final_df[['game_id', 'date']].drop_duplicates()
    pitcher_df = add_pitcher_rolling_stats(pitcher_df, game_dates)
    pitcher_df = add_bullpen_rolling_stats(pitcher_df, final_df)

    final_df_with_pitchers = merge_pitcher_stats_to_games(final_df, pitcher_df)
    final_df_with_pitchers = merge_bullpen_stats_to_games(final_df_with_pitchers, pitcher_df)
    return final_df_with_pitchers