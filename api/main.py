

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler


from live_data_sources.MLB_game.mlb_api import get_game_statuses
from live_data_sources.PolyMarket.polymarket_API import match_polymarket_to_game, get_MLB_markets, parse_polymarket_odds
from Machine_Learning_Pipeline.predict_pipeline import compute_predictions
from Machine_Learning_Pipeline.train_model import main as retrain

app = FastAPI(title="MLB Predictions API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # your React dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


_predictions = {'games': {}, 'model_accuracy': None}

scheduler = BackgroundScheduler()


def retrain_then_refresh():
    retrain()              # your existing daily retrain
    refresh_predictions()  # reload the new model, recompute

def refresh_predictions():
    global _predictions
    _predictions = compute_predictions()

@app.on_event("startup")
def startup():
    refresh_predictions()
    scheduler.add_job(refresh_predictions, "cron", hour="*")   # pitchers get announced through the day
    scheduler.add_job(retrain_then_refresh, "cron", hour=11)
    scheduler.start()

@app.get("/api/games")
def api_games():
    try:
        statuses = get_game_statuses()
    except Exception:
        statuses = {}
    market_games = get_MLB_markets()          # keep your short cache here

    out = []
    for gid, g in _predictions['games'].items():
        market = match_polymarket_to_game(market_games, g['home_team_name'], g['away_team_name'])
        home_odds, away_odds = parse_polymarket_odds(market, g['home_team_name'], g['away_team_name'])
        s = statuses.get(gid, {})
        p = g['home_prediction']

        out.append({
            **g,
            'home_prediction': p,
            'away_prediction': (1 - p) if p is not None else None,
            'home_polymarket': home_odds,
            'away_polymarket': away_odds,
            'is_live': s.get('state') == 'Live',
            'is_final': s.get('state') == 'Final',
            'inning': f'{s.get("half", "")} {s.get("inning", "")}'.strip() or None,
        })

    return {'games': out, 'model_accuracy': _predictions['model_accuracy']}
@app.get("/")
def root():
    return {"status": "MLB Predictions API is running"}