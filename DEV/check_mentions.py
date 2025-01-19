import requests
import os
from dotenv import load_dotenv
import json
import time

load_dotenv()
bearer_token = os.getenv("BEARER_TOKEN")
username = "TheFightAgent"
user_id_url = f"https://api.twitter.com/2/users/by/username/{username}"
headers = {"Authorization": f"Bearer {bearer_token}"}
user_id_response = requests.get(user_id_url, headers=headers)
if user_id_response.status_code != 200:
    print(f"Error fetching user ID: {user_id_response.status_code}, {user_id_response.text}")
else:
    # Get rate limit info from user_id response
    rate_limit_remaining = user_id_response.headers.get("x-rate-limit-remaining")
    rate_limit_reset = user_id_response.headers.get("x-rate-limit-reset")
    
    user_id = user_id_response.json().get("data", {}).get("id")
    if user_id:
        mentions_url = f"https://api.twitter.com/2/users/{user_id}/mentions"
        params = {
            # "max_results": 100,
            "max_results": 10,
            "tweet.fields": "id,created_at,text,author_id",
        }
        mentions_response = requests.get(mentions_url, headers=headers, params=params)
        if mentions_response.status_code != 200:
            print(f"Error fetching mentions: {mentions_response.status_code}, {mentions_response.text}")
        else:
            mentions_data = mentions_response.json()
            # print("Mentions found:", mentions_data)
            
            with open('data/mentions.json', 'w') as f:
                json.dump(mentions_data, f, indent=4)
            print("Mentions saved to data/mentions.json\n")

            # Print each tweet's details in a formatted way
            for tweet in mentions_data.get('data', []):
                print(f"Tweet ID: {tweet['id']}")
                print(f"Author ID: {tweet['author_id']}")
                print(f"Created At: {tweet['created_at']}")
                print(f"Text: {tweet['text']}")
                print("-" * 40)
        
        # After all operations are complete, print rate limit status
        if rate_limit_remaining and rate_limit_reset:
            reset_time = time.strftime('%Y-%m-%d %I:%M:%S %p', time.localtime(int(rate_limit_reset)))
            print("\nRate Limit Status:")
            print(f"Rate Limit Remaining: {rate_limit_remaining} requests")
            print(f"Rate Limit Resets At: {reset_time} (local time)")
    else:
        print("Failed to retrieve user ID.")



### CHECKING EVERY 15 MINUTES ###
# import requests
# import os
# import json
# import time
# from dotenv import load_dotenv

# load_dotenv()
# bearer_token = os.getenv("BEARER_TOKEN")
# username = "TheFightAgent"
# user_id_url = f"https://api.twitter.com/2/users/by/username/{username}"
# headers = {"Authorization": f"Bearer {bearer_token}"}

# def get_user_id():
#     response = requests.get(user_id_url, headers=headers)
#     if response.status_code == 200:
#         return response.json().get("data", {}).get("id")
#     else:
#         print(f"Error fetching user ID: {response.status_code}, {response.text}")
#         return None

# def get_mentions(user_id):
#     mentions_url = f"https://api.twitter.com/2/users/{user_id}/mentions"
#     params = {
#         "max_results": 5,
#         "tweet.fields": "id,created_at,text,author_id",
#     }
#     while True:
#         response = requests.get(mentions_url, headers=headers, params=params)
#         if response.status_code == 200:
#             return response.json()
#         elif response.status_code == 429:
#             print("Rate limit exceeded. Waiting before retrying...")
#             time.sleep(15 * 60)  # Wait for 15 minutes
#         else:
#             print(f"Error fetching mentions: {response.status_code}, {response.text}")
#             return None

# def main():
#     user_id = get_user_id()
#     if user_id:
#         mentions_data = get_mentions(user_id)
#         if mentions_data:
#             print("Mentions found:", mentions_data)
#             with open('data/mentions.json', 'w') as f:
#                 json.dump(mentions_data, f, indent=4)
#             print("Mentions saved to data/mentions.json")
#         else:
#             print("Failed to retrieve mentions.")
#     else:
#         print("Failed to retrieve user ID.")

# if __name__ == "__main__":
#     main()