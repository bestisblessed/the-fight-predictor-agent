import tweepy
import os
import sys
from dotenv import load_dotenv

# Check command line arguments
if len(sys.argv) != 2:
    print("Usage: python post_tweet2.py <tweet_id>")
    sys.exit(1)

tweet_id = sys.argv[1]
file_path = f'responses/{tweet_id}.txt'

if not os.path.exists(file_path):
    print(f"Error: File not found: {file_path}")
    sys.exit(1)

# Read content for Twitter
with open(file_path, 'r', encoding='utf-8') as file:
    content = file.read()

# Set up Twitter client
load_dotenv()
client = tweepy.Client(
    consumer_key=os.getenv("TWITTER_API_KEY"),
    consumer_secret=os.getenv("TWITTER_API_SECRET"),
    access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
    access_token_secret=os.getenv("TWITTER_ACCESS_SECRET")
)

# Post to Twitter
try:
    response = client.create_tweet(text=content)
    print(f"Tweet posted successfully: {response.data['id']}")
except Exception as e:
    print(f"Error posting tweet: {e}")