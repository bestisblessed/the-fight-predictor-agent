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

# Initialize the API object for media uploads
auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

# Initialize the Client object for creating tweets
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

try:
    # Check for image files with the tweet ID prefix
    # image_files = glob.glob(f"files/{tweet_id}*.*")
    # image_files = glob.glob(f"/home/trinity/the-fight-predictor-agent/PRODUCTION/files/{tweet_id}*.*")
    image_file = f"/home/trinity/the-fight-predictor-agent/PRODUCTION/files/{tweet_id}.png"
    media_ids = []

    if os.path.exists(image_file):
        media = api.media_upload(image_file)
        media_ids.append(media.media_id)
        response = client.create_tweet(
            text=reply_text,
            quote_tweet_id=tweet_id,  # Quote the tweet
            media_ids=media_ids,  # Attach media if available
            # geo={'place_id': '3b77caf94bfc81fe'},  # Las Vegas geo-tagging
        )
    else:
        response = client.create_tweet(
            text=reply_text,
            quote_tweet_id=tweet_id,  # Quote the tweet
            # geo={'place_id': '3b77caf94bfc81fe'}  # Las Vegas geo-tagging
        )

    # # Create the tweet, with or without media
    # response = client.create_tweet(
    #     text=reply_text,
    #     quote_tweet_id=tweet_id,  # Quote the tweet
    #     geo={'place_id': '3b77caf94bfc81fe'},  # Las Vegas geo-tagging
    #     media_ids=media_ids if media_ids else None  # Attach media if available
    # )


    # print(f"Replied to tweet {tweet_id} with ID: {response.data['id']}")
    print(f"Tweeted with ID: {response.data['id']}")


except tweepy.errors.Forbidden as e:
    print("Error: Forbidden - Check your app's access level or API tier.")
    print(f"Details: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
