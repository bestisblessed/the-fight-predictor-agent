# import os
# import tweepy

# # 1. Load credentials from environment variables (or replace with your own).
# API_KEY = os.getenv("TWITTER_API_KEY")
# API_SECRET = os.getenv("TWITTER_API_SECRET")
# ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
# ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# # 2. Authenticate to Twitter
# auth = tweepy.OAuth1UserHandler(
#     API_KEY,
#     API_SECRET,
#     ACCESS_TOKEN,
#     ACCESS_SECRET
# )
# api = tweepy.API(auth)

# # 3. Post a tweet
# try:
#     tweet_text = "Hello, Twitter! #MyFirstTweetAsAnAutonomousAgent"
#     response = api.update_status(status=tweet_text)
#     print(f"Tweet posted! ID: {response.id}")
# except Exception as e:
#     print(f"Error posting tweet: {e}")

import os
import tweepy
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load credentials from environment variables or replace with your own
API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET = os.getenv("TWITTER_API_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# Check if all required credentials are available
if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
    print("Error: Missing one or more Twitter API credentials.")
    exit()

# Authenticate to Twitter using OAuth 2.0 (for API v2 compatibility)
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

# Function to post a tweet using Twitter API v2
def post_tweet_v2(text):
    try:
        response = client.create_tweet(text=text)
        print(f"Tweet posted! ID: {response.data['id']}")
    except tweepy.errors.Forbidden as e:
        print("Error: Forbidden - Check your app's access level or API tier.")
        print(f"Details: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
# Main program
def main():
    # tweet_text = "Hello, Twitter! #MyFirstTweetAsAnAutonomousAgent"
    tweet_text = input("Enter your tweet: ")
    post_tweet_v2(tweet_text)

if __name__ == "__main__":
    main()

