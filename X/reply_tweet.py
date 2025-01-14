# # # # import os
# # # # import tweepy

# # # # API_KEY = os.getenv("TWITTER_API_KEY")
# # # # API_SECRET = os.getenv("TWITTER_API_SECRET")
# # # # ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
# # # # ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# # # # auth = tweepy.OAuth1UserHandler(
# # # #     API_KEY,
# # # #     API_SECRET,
# # # #     ACCESS_TOKEN,
# # # #     ACCESS_SECRET
# # # # )
# # # # api = tweepy.API(auth)

# # # # try:
# # # #     # Let's say you want to reply to a specific tweet ID
# # # #     tweet_id_to_reply = 1234567890  # Replace with a real tweet ID
# # # #     reply_text = "@username Thanks for tweeting about Python!"
    
# # # #     response = api.update_status(
# # # #         status=reply_text,
# # # #         in_reply_to_status_id=tweet_id_to_reply,
# # # #         auto_populate_reply_metadata=True
# # # #     )
# # # #     print(f"Replied to tweet {tweet_id_to_reply} with ID: {response.id}")
# # # # except Exception as e:
# # # #     print(f"Error replying to tweet: {e}")

# # # import os
# # # import tweepy
# # # from dotenv import load_dotenv
# # # import json

# # # load_dotenv()
# # # API_KEY = os.getenv("TWITTER_API_KEY")
# # # API_SECRET = os.getenv("TWITTER_API_SECRET")
# # # ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
# # # ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# # # # Check if all required credentials are available
# # # if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
# # #     print("Error: Missing one or more Twitter API credentials.")
# # #     exit()

# # # # Authenticate to Twitter
# # # auth = tweepy.OAuth1UserHandler(
# # #     API_KEY,
# # #     API_SECRET,
# # #     ACCESS_TOKEN,
# # #     ACCESS_SECRET
# # # )
# # # api = tweepy.API(auth)

# # # # Mentions data from your output
# # # mentions_data = {
# # #     'data': [
# # #         {'author_id': '1222289587474661381', 'id': '1879217179545178231', 'text': '@TheFightAgent fuck yes', 'created_at': '2025-01-14T17:21:04.000Z'},
# # #         {'author_id': '1222289587474661381', 'id': '1879204153257517208', 'text': 'Analyze+tell me about Islam Makachev @TheFightAgent', 'created_at': '2025-01-14T16:29:18.000Z'},
# # #         {'author_id': '1411034073808650247', 'id': '1879092255598002467', 'text': '@TheFightAgent suppppppp', 'created_at': '2025-01-14T09:04:40.000Z'}
# # #     ],
# # #     'meta': {'result_count': 3, 'newest_id': '1879217179545178231', 'oldest_id': '1879092255598002467'}
# # # }

# # # try:
# # #     # Get the ID of the latest mention
# # #     latest_mention_id = mentions_data['meta']['newest_id']
# # #     latest_mention_text = next(item for item in mentions_data['data'] if item['id'] == latest_mention_id)['text']
    
# # #     # Prepare the reply text
# # #     reply_text = f"@{latest_mention_text.split()[0]} Thanks for the mention!"

# # #     # Reply to the latest mention
# # #     response = api.update_status(
# # #         status=reply_text,
# # #         in_reply_to_status_id=latest_mention_id,
# # #         auto_populate_reply_metadata=True
# # #     )
# # #     print(f"Replied to tweet {latest_mention_id} with ID: {response.id}")
# # # except Exception as e:
# # #     print(f"Error replying to tweet: {e}")


# # import os
# # import tweepy
# # import json
# # from dotenv import load_dotenv

# # # Load environment variables from .env file
# # load_dotenv()

# # # Load credentials from environment variables
# # API_KEY = os.getenv("TWITTER_API_KEY")
# # API_SECRET = os.getenv("TWITTER_API_SECRET")
# # ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
# # ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# # # Check if all required credentials are available
# # if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
# #     print("Error: Missing one or more Twitter API credentials.")
# #     exit()

# # # Authenticate to Twitter using OAuth 1.0a
# # auth = tweepy.OAuth1UserHandler(
# #     API_KEY,
# #     API_SECRET,
# #     ACCESS_TOKEN,
# #     ACCESS_SECRET
# # )
# # api = tweepy.API(auth)

# # # Example: Reply to the latest mention
# # try:
# #     # Load mentions from the saved JSON file
# #     with open('data/mentions.json', 'r') as f:
# #         mentions_data = json.load(f)
    
# #     # Get the ID of the latest mention
# #     latest_mention_id = mentions_data['meta']['newest_id']
# #     latest_mention_text = next(item for item in mentions_data['data'] if item['id'] == latest_mention_id)['text']
    
# #     # Prepare the reply text
# #     reply_text = f"@{latest_mention_text.split()[0]} Thanks for the mention!"

# #     # Reply to the latest mention
# #     response = api.update_status(
# #         status=reply_text,
# #         in_reply_to_status_id=latest_mention_id,
# #         auto_populate_reply_metadata=True
# #     )
# #     print(f"Replied to tweet {latest_mention_id} with ID: {response.id}")
# # except Exception as e:
# #     print(f"Error replying to tweet: {e}")

# import os
# import tweepy
# import json
# from dotenv import load_dotenv

# # Load environment variables from .env file
# load_dotenv()

# # Load credentials from environment variables
# API_KEY = os.getenv("TWITTER_API_KEY")
# API_SECRET = os.getenv("TWITTER_API_SECRET")
# ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
# ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# # Check if all required credentials are available
# if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
#     print("Error: Missing one or more Twitter API credentials.")
#     exit()

# # Authenticate to Twitter using OAuth 2.0
# client = tweepy.Client(
#     consumer_key=API_KEY,
#     consumer_secret=API_SECRET,
#     access_token=ACCESS_TOKEN,
#     access_token_secret=ACCESS_SECRET
# )

# # Example: Reply to the latest mention
# try:
#     # Load mentions from the saved JSON file
#     with open('data/mentions.json', 'r') as f:
#         mentions_data = json.load(f)
    
#     # Get the ID of the latest mention
#     latest_mention_id = mentions_data['meta']['newest_id']
#     latest_mention_text = next(item for item in mentions_data['data'] if item['id'] == latest_mention_id)['text']
    
#     # Prepare the reply text
#     reply_text = f"@{latest_mention_text.split()[0]} Thanks for the mention!"

#     # Reply to the latest mention
#     response = client.create_tweet(
#         text=reply_text,
#         in_reply_to_tweet_id=latest_mention_id
#     )
#     print(f"Replied to tweet {latest_mention_id} with ID: {response.data['id']}")
# except tweepy.errors.Forbidden as e:
#     print("Error: Forbidden - Check your app's access level or API tier.")
#     print(f"Details: {e}")
# except Exception as e:
#     print(f"Unexpected error: {e}")


import os
import tweepy
import json
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load credentials from environment variables
API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET = os.getenv("TWITTER_API_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# Check if all required credentials are available
if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
    print("Error: Missing one or more Twitter API credentials.")
    exit()

# Authenticate to Twitter using OAuth 2.0
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

# Example: Reply to all mentions
try:
    # Load mentions from the saved JSON file
    with open('data/mentions.json', 'r') as f:
        mentions_data = json.load(f)
    
    # Loop through each mention and reply
    for mention in mentions_data['data']:
        mention_id = mention['id']
        mention_text = mention['text']
        
        # Extract the username from the mention text
        username = mention_text.split()[0]
        
        # Prepare the reply text
        # reply_text = f"{mention_text.split()[0]} Thanks for the mention!"
        reply_text = f"{username} Thanks for the mention!!!!!!"

        # Reply to the mention
        response = client.create_tweet(
            text=reply_text,
            in_reply_to_tweet_id=mention_id
        )
        print(f"Replied to tweet {mention_id} with ID: {response.data['id']}")
        
        # Sleep for 3 seconds between replies
        time.sleep(3)
except tweepy.errors.Forbidden as e:
    print("Error: Forbidden - Check your app's access level or API tier.")
    print(f"Details: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")