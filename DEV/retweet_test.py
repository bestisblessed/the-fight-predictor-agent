import os
import tweepy
from dotenv import load_dotenv

### Retweet a tweet using v2 Endpoint ###

load_dotenv()
API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET = os.getenv("TWITTER_API_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

tweet_id = input("Enter the tweet ID to retweet: ")
try:
    response = client.retweet(tweet_id)
    if response.data:
        print(f"Successfully retweeted tweet ID: {tweet_id}")
    else:
        print("Failed to retweet. Please check the tweet ID and your permissions.")
except tweepy.errors.TweepyException as e:
    print(f"Error retweeting: {e}")
