import requests
import json

#TEAM LISTS/IDS
team_lists = "https://statsapi.mlb.com/api/v1/teams"

#Connects to API Endpoint
def connect_team_endpoint():
    response = requests.get(team_lists)

    if response.status_code != 200:
        raise Exception(f"Error {response.status_code} getting team stats")

    return response.json()


#Gets college teams from data
def get_college_teams(data):

    college_teams = []
    for team in data["teams"]:
        if team["sport"]["name"] == "College Baseball":
            college_teams.append(team)

    save_json(data=college_teams, talent_level="College Baseball")

#Gets MLB teams from data
def get_MLB_teams(data):

    MLB = []
    for team in data["teams"]:
        if team["sport"]["name"] == "Major League Baseball":
            MLB.append(team)

    save_json(data=MLB, talent_level="Major League Baseball")



#SAVES data based on talent level
def save_json(data, talent_level):
    if talent_level == "College Baseball":
        with open("college_output.json", "w") as file:
            json.dump(data, file, indent=4)
    elif talent_level == "Major League Baseball":
        with open("MLB_output.json", "w") as file:
            json.dump(data, file, indent=4)




data = connect_team_endpoint()
get_college_teams(data=data)
get_MLB_teams(data=data)
