import json
import pandas as pd
import glob
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))



def open_json(filepath):
    with open(filepath, 'r') as file:
        data = json.load(file)
    return data

#Optimal year is 2023-2026
def clean_json_data(min_year=2023):
    filepaths = sorted(glob.glob(os.path.join(SCRIPT_DIR, 'Schedule', 'Schedule_output_*.json')))
    print(f"Found {len(filepaths)} season files: {filepaths}")
    filepaths = [f for f in filepaths if int(f.split('_')[-1].split('.')[0]) >= min_year]
    print(f"Found {len(filepaths)} season files: {filepaths}")


    games = []
    skipped = 0
    for filepath in filepaths:
        data = open_json(filepath)
        for date_entry in data["dates"]:
            for game in date_entry["games"]:
                if game['status']['detailedState'] != 'Final':
                    continue
                t = game['teams']

                # skip games missing critical fields (rare edge cases)
                if 'isWinner' not in t['home'] or 'isWinner' not in t['away']:
                    skipped += 1
                    continue

                # home team's row
                games.append({
                    'date': date_entry['date'],
                    'game_id': game['gamePk'],
                    'team_id': t['home']['team']['id'],
                    'team_name': t['home']['team']['name'],
                    'opponent_id': t['away']['team']['id'],
                    'opponent_name': t['away']['team']['name'],
                    'runs_scored': t['home']['score'],
                    'runs_allowed': t['away']['score'],
                    'win': t['home']['isWinner'],
                    'is_home': True,
                })

                # away team's row
                games.append({
                    'date': date_entry['date'],
                    'game_id': game['gamePk'],
                    'team_id': t['away']['team']['id'],
                    'team_name': t['away']['team']['name'],
                    'opponent_id': t['home']['team']['id'],
                    'opponent_name': t['home']['team']['name'],
                    'runs_scored': t['away']['score'],
                    'runs_allowed': t['home']['score'],
                    'win': t['away']['isWinner'],
                    'is_home': False,
                })

    print(f"Skipped {skipped} games missing isWinner")

    long_df = pd.DataFrame(games)
    long_df['date'] = pd.to_datetime(long_df['date'])
    long_df = long_df.drop_duplicates(subset=['game_id', 'team_id'])
    long_df = long_df.sort_values(['team_id', 'date']).reset_index(drop=True)
    return long_df


def add_rolling_stats(long_df, windows=(5, 10, 20)):
    long_df = long_df.sort_values(['team_id', 'date']).reset_index(drop=True)
    long_df['run_diff'] = long_df['runs_scored'] - long_df['runs_allowed']

    # days since this team's last game
    long_df['days_rest'] = long_df.groupby('team_id')['date'].diff().dt.days
    long_df['days_rest'] = long_df['days_rest'].clip(upper=5)

    grouped_win = long_df.groupby('team_id')['win']
    grouped_diff = long_df.groupby('team_id')['run_diff']

    for window in windows:
        long_df[f'win_pct_last{window}'] = grouped_win.transform(
            lambda s: s.shift(1).rolling(window, min_periods=1).mean()
        )
        long_df[f'run_diff_last{window}'] = grouped_diff.transform(
            lambda s: s.shift(1).rolling(window, min_periods=1).mean()
        )


    long_df['win_pct_season'] = grouped_win.transform(lambda s: s.shift(1).expanding(min_periods=1).mean())
    long_df['run_diff_season'] = grouped_diff.transform(lambda s: s.shift(1).expanding(min_periods=1).mean())
    return long_df


def build_game_level_df(long_df):
    home_side = long_df[long_df['is_home']].copy()
    away_side = long_df[~long_df['is_home']].copy()

    stat_cols = ['win_pct_last5', 'run_diff_last5', 'win_pct_last10', 'run_diff_last10',
                 'win_pct_last20', 'run_diff_last20', 'win_pct_season', 'run_diff_season',
                 'days_rest']

    home_side = home_side.rename(columns={c: f'home_{c}' for c in stat_cols})
    away_side = away_side.rename(columns={c: f'away_{c}' for c in stat_cols})

    final_df = home_side[['game_id', 'date', 'team_id', 'win'] + [f'home_{c}' for c in stat_cols]].merge(
        away_side[['game_id', 'team_id'] + [f'away_{c}' for c in stat_cols]],
        on='game_id',
        suffixes=('_home', '_away')
    )
    final_df = final_df.rename(columns={'team_id_home': 'home_team_id', 'team_id_away': 'away_team_id', 'win': 'home_win'})
    final_df = final_df.dropna(subset=[f'home_{c}' for c in stat_cols] + [f'away_{c}' for c in stat_cols])
    return final_df


def get_training_data():
    """Single entry point — everything else calls this."""
    long_df = clean_json_data()
    long_df = clean_json_data()
    long_df = add_rolling_stats(long_df)
    final_df = build_game_level_df(long_df)
    return final_df


if __name__ == '__main__':
    df = get_training_data()
    print(df.head(50))