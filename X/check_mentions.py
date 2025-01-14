import requests
import os
from dotenv import load_dotenv
load_dotenv()
bearer_token = os.getenv("BEARER_TOKEN")
username = "TheFightAgent"
user_id_url = f"https://api.twitter.com/2/users/by/username/{username}"
headers = {"Authorization": f"Bearer {bearer_token}"}
user_id_response = requests.get(user_id_url, headers=headers)
if user_id_response.status_code != 200:
    print(f"Error fetching user ID: {user_id_response.status_code}, {user_id_response.text}")
else:
    user_id = user_id_response.json().get("data", {}).get("id")
    if user_id:
        mentions_url = f"https://api.twitter.com/2/users/{user_id}/mentions"
        params = {
            "max_results": 100,
            "tweet.fields": "id,created_at,text,author_id",
        }
        mentions_response = requests.get(mentions_url, headers=headers, params=params)
        if mentions_response.status_code != 200:
            print(f"Error fetching mentions: {mentions_response.status_code}, {mentions_response.text}")
        else:
            mentions_data = mentions_response.json()
            print("Mentions found:", mentions_data)
    else:
        print("Failed to retrieve user ID.")
