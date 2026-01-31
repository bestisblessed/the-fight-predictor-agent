import os
import subprocess
import sys
import time
from pathlib import Path

import openai
from dotenv import load_dotenv
from docx import Document
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle

sys.path.append(str(Path(__file__).resolve().parents[1]))

from responses_api_utils import (
    create_response,
    default_cache_path,
    extract_text,
    get_dataset_file_ids,
)
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    print("API key is required to run the chatbot.")
    exit()

print("MMA AI Chatbot Initialized - Processing Tweets.")
client = openai.OpenAI(api_key=openai.api_key)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SYSTEM_PROMPT = os.getenv("OPENAI_SYSTEM_PROMPT")
DATA_DIR = os.getenv("DATA_DIR", "data")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs("responses", exist_ok=True)
os.makedirs("files", exist_ok=True)

tweets_file = os.path.join(DATA_DIR, "TheFightAgentMentions.docx")
document = Document(tweets_file)
tweets = []
tweet_data = {}  

processed_ids_file = os.path.join(DATA_DIR, "processed_tweet_ids.txt")
processed_ids = set()
try:
    with open(processed_ids_file, "r") as f:
        processed_ids = {line.strip() for line in f if line.strip()}
except FileNotFoundError:
    print("No previous tweet ID log found, starting fresh")

current_tweet = None
current_id = None
temp_tweet = None  

for paragraph in document.paragraphs:
    text = paragraph.text.strip()
    if text.startswith('-----------------------------------'):
        current_id = None
        temp_tweet = None  
    elif text.startswith('Tweet:'):
        temp_tweet = text.replace('Tweet:', '').strip()  
    elif text.startswith('Link:'):
        current_id = text.split('/')[-1].strip()
        print(f"Found Link ID: {current_id}")
        if temp_tweet and current_id and current_id not in processed_ids:
            tweets.append(temp_tweet)
            tweet_data[temp_tweet] = current_id
            print(f"Added tweet with ID: {current_id}")

print(f"\nFound new tweets: {len(tweets)}")
if not tweets:
    print("No new tweets found to process.")
    exit()

print(f"Found {len(tweets)} new tweets to process.")

try:
    dataset_file_ids = get_dataset_file_ids(
        client,
        data_dir=DATA_DIR,
        cache_path=default_cache_path(DATA_DIR),
    )
except FileNotFoundError as exc:
    print(str(exc))
    exit()

for tweet in tweets:
    print(f"\nTweet: {tweet}")
    tweet_id = tweet_data[tweet]
    
    try:
        # Generate new response using OpenAI Responses API
        response = create_response(
            client,
            MODEL,
            tweet,
            dataset_file_ids,
            system_prompt=SYSTEM_PROMPT,
        )
        print("Processing...")

        ai_response = extract_text(response)
        if not ai_response:
            print("No valid AI response found in response output.")
            continue  # Skip to next tweet if no valid response

        print(f"Extracted AI Response: {ai_response}")
            
        # Save response to local file
        response_file_path = f'responses/{tweet_id}.txt'
        try:
            with open(response_file_path, 'w', encoding='utf-8') as f:
                f.write(ai_response)
            print(f"Saved response to {response_file_path}")
            
        except Exception as e:
            print(f"Error saving response file: {e}")
            continue
        
        # Use the response to reply on Twitter
        success = False
        try:
            result = subprocess.run(
                ["python", "upload_responses_to_docs.py", tweet_id],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"Reply script output: {result.stdout}")
            if "Too Many Requests" in result.stdout:
                print("Failed to send reply - Rate limit exceeded")
            else:
                print("Successfully sent reply to Twitter")
                success = True
        except subprocess.CalledProcessError as e:
            print(f"Failed to send reply to Twitter. Error code: {e.returncode}")
            print(f"Error output: {e.stderr}")
            print(f"Standard output: {e.stdout}")

        if success:
            with open(processed_ids_file, "a") as f:
                f.write(f"{tweet_id}")
                f.write("")  
                f.write("\n")  
            print(f"Logged processed tweet ID: {tweet_id}")
            
    except Exception as e:
        print(f"Error processing tweet: {e}")
        continue
    
    time.sleep(5)
