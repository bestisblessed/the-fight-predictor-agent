import os
import tweepy
import sys
from dotenv import load_dotenv
from pathlib import Path
if len(sys.argv) != 2:
    print("Usage: python reply_single_tweet.py <tweet_id>")
    exit(1)
tweet_id = sys.argv[1]
response_file = Path(f'responses/{tweet_id}.txt')
if not response_file.exists():
    print(f"Error: No response file found for tweet ID {tweet_id}")
    exit(1)
with open(response_file, 'r', encoding='utf-8') as f:
    reply_text = f.read()
load_dotenv()
API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET = os.getenv("TWITTER_API_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
    print("Error: Missing one or more Twitter API credentials.")
    exit(1)
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)
try:
    response = client.create_tweet(
        text=reply_text,
        in_reply_to_tweet_id=tweet_id
    )
    print(f"Replied to tweet {tweet_id} with ID: {response.data['id']}")
except tweepy.errors.Forbidden as e:
    print("Error: Forbidden - Check your app's access level or API tier.")
    print(f"Details: {e}")
except tweepy.errors.TooManyRequests as e:
    print("Error: Rate limit exceeded. Please wait before trying again.")
    print(f"Details: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")