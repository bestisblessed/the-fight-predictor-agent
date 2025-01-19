import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()
bearer_token = os.getenv("BEARER_TOKEN")

def search_recent_tweets(query, max_results=10):
    """
    Searches recent tweets based on a query.
    Args:
        query (str): Search query (e.g., keywords, hashtags).
        max_results (int): Maximum number of tweets to retrieve (1-100).
    Returns:
        dict: Response data from the API.
    """
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    params = {
        "query": query,
        "max_results": max_results,
        "tweet.fields": "id,text,author_id,created_at",
    }
    
    while True:
        print("Sending request to Twitter API...")
        response = requests.get(url, headers=headers, params=params)
        print(f"Response status code: {response.status_code}")
        
        if response.status_code == 429:
            print("Rate limit exceeded. Waiting to retry...")
            time.sleep(15 * 60)  # Wait for 15 minutes
        elif response.status_code != 200:
            print(f"Error searching tweets: {response.status_code}, {response.text}")
            return None
        else:
            data = response.json()
            print("Received data:", data)
            return data

# Example usage
if __name__ == "__main__":
    # tweets = search_recent_tweets("example query")
    # tweets = search_recent_tweets("openai OR gpt-4") # Key Words
    # tweets = search_recent_tweets("#Python") # Hashtags
    tweets = search_recent_tweets("from:TheFightAgent")
    if tweets:
        print("Tweets found:", tweets)
    else:
        print("No tweets found or an error occurred.")
