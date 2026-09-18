

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Machine_Learning_Pipeline.predict_pipeline import get_predictions_for_upcoming_games

app = FastAPI(title="MLB Predictions API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # your React dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/games")
def get_games():
    """Returns predictions + polymarket odds for upcoming MLB games."""
    # try:
    #     return get_predictions_for_upcoming_games()
    # except Exception as e:
    #     return {"error": str(e)}
    return get_predictions_for_upcoming_games()


@app.get("/")
def root():
    return {"status": "MLB Predictions API is running"}