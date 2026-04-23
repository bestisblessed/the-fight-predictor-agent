import os
import tweepy
import json
import time
import random
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET = os.getenv("TWITTER_API_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
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

# List of emojis to randomly choose from (no duplicates will be used)
available_emojis = ["😊", "🎉", "👋", "💪", "🔥", "✨", "🌟", "🎈", "🎊", "👍", "💯", "🙌", "🤗", "😎", "🚀"]

# Reply to all mentions
try:
    with open('data/mentions.json', 'r') as f:
        mentions_data = json.load(f)
    
    for mention in mentions_data['data']:
        mention_id = mention['id']
        mention_text = mention['text']
        
        username = mention_text.split()[0]
        
        if available_emojis:
            chosen_emoji = random.choice(available_emojis)
            available_emojis.remove(chosen_emoji)
            reply_text = f"{username} {chosen_emoji}"
            response = client.create_tweet(
                text=reply_text,
                in_reply_to_tweet_id=mention_id
            )
            print(f"Replied to tweet {mention_id} with ID: {response.data['id']}")
            time.sleep(3)
        else:
            print("Warning: Ran out of unique emojis to use!")
            break
except tweepy.errors.Forbidden as e:
    print("Error: Forbidden - Check your app's access level or API tier.")
    print(f"Details: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")