import os
import tweepy
import sys
from dotenv import load_dotenv

# Check command line arguments
if len(sys.argv) < 3:
    print("Usage: python reply_single_tweet.py <tweet_id> <reply_text...>")
    exit(1)

tweet_id = sys.argv[1]
reply_text = ' '.join(sys.argv[2:])  # Join all remaining arguments as the reply text

load_dotenv()
API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET = os.getenv("TWITTER_API_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
    print("Error: Missing one or more Twitter API credentials.")
    exit()

client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

# Reply to a specific tweet ID
try:
    # tweet_id = "1879384998589124828"
    # reply_text = "Greetings"
    response = client.create_tweet(
        text=reply_text,
        in_reply_to_tweet_id=tweet_id
    )
    print(f"Replied to tweet {tweet_id} with ID: {response.data['id']}")
except tweepy.errors.Forbidden as e:
    print("Error: Forbidden - Check your app's access level or API tier.")
    print(f"Details: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
