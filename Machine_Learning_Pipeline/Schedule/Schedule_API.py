import requests
import json
from datetime import date, timedelta


def connect_schedule_endpoint(start_date, end_date):
    schedule = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={start_date}&endDate={end_date}"
    response = requests.get(schedule)

    if response.status_code != 200:
        raise Exception(f"Error {response.status_code} fetching schedule")

    return response.json()

yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')

# each season's regular-season date range 
seasons = {
    2019: ("2019-03-20", "2019-09-29"),
    2020: ("2020-07-23", "2020-09-27"),
    2021: ("2021-04-01", "2021-10-03"),
    2022: ("2022-04-07", "2022-10-05"),
    2023: ("2023-03-30", "2023-10-01"),
    2024: ("2024-03-20", "2024-09-29"),
    2025: ("2025-03-18", "2025-09-28"),
    2026: ("2026-03-25", yesterday),
}

#goes through seasons and collects schedules and writes into json
for year, (start_date, end_date) in seasons.items():
    data = connect_schedule_endpoint(start_date, end_date)
    with open(f"Schedule_output_{year}.json", "w") as file:
        json.dump(data, file, indent=4)
    print(f"Saved {year}: {start_date} to {end_date}")