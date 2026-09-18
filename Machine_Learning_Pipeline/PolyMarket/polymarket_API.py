import requests
import json
from datetime import datetime, timezone, timedelta

url = "https://gamma-api.polymarket.com/events"

def connect_polymarket_endpoint():

    params = {
    "series_id": "3",
    "active": "true",
    "closed": "false",
    }

    response = requests.get(url, params=params)

    if response.status_code != 200:
        raise Exception(f"Error {response.status_code} getting team stats")

    return response.json()



def get_MLB_markets():
    markets = connect_polymarket_endpoint()
    games = []
    seen_titles = set()
    now = datetime.now(timezone.utc)

    for game in markets:
        title = game.get("title", "")
        if "Player Props" in title or "9th Inning Winner" in title:
            continue
        if title in seen_titles:
            continue
        seen_titles.add(title)

        event = {"game_title": title, "date_time": "", "outcomes": "", "outcomePrices": ""}
        for market in game.get("markets") or []:
            if market.get("question") == event["game_title"]:
                event["date_time"] = market.get("gameStartTime")
                event["outcomes"] = market.get("outcomes")
                event["outcomePrices"] = market.get("outcomePrices")

        if not event["date_time"]:
            continue

        game_time = datetime.fromisoformat(event["date_time"].replace('+00', '+00:00'))

        # skip only games that started more than ~5 hours ago (long enough for any game to have finished)
        if game_time < now - timedelta(hours=5):
            continue

        games.append(event)

    return games
    

