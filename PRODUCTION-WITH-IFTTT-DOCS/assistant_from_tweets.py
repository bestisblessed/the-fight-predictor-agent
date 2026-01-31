"""
MMA AI Agent - Twitter Mention Responder (IFTTT + Google Docs variant)
Migrated from OpenAI Assistants API to Responses API with Code Interpreter

This script processes tweets, uses OpenAI's Responses API with Code Interpreter,
and uploads responses to Google Docs.
"""

import openai
import time
import requests
import os
import json
from dotenv import load_dotenv
from PIL import Image
import io
from docx import Document
import subprocess
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
import os.path

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    print("API key is required to run the chatbot.")
    exit()

print("MMA AI Chatbot Initialized - Processing Tweets (Responses API).")
client = openai.OpenAI(api_key=openai.api_key)

os.makedirs('data', exist_ok=True)
os.makedirs('responses', exist_ok=True)
os.makedirs('files', exist_ok=True)

# ============================================================================
# File Management for Code Interpreter
# ============================================================================

DATASET_FILES = [
    'data/fighter_info.csv',
    'data/event_data_sherdog.csv'
]

FILE_IDS_CACHE = 'data/uploaded_file_ids.json'


def load_cached_file_ids():
    """Load previously uploaded file IDs from cache."""
    if os.path.exists(FILE_IDS_CACHE):
        try:
            with open(FILE_IDS_CACHE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_cached_file_ids(file_ids):
    """Save uploaded file IDs to cache."""
    with open(FILE_IDS_CACHE, 'w') as f:
        json.dump(file_ids, f, indent=2)


def verify_file_exists(file_id):
    """Check if a file ID is still valid in OpenAI."""
    try:
        client.files.retrieve(file_id)
        return True
    except Exception:
        return False


def upload_datasets():
    """Upload MMA datasets to OpenAI for use with Code Interpreter."""
    cached = load_cached_file_ids()
    file_ids = []
    updated = False
    
    for filepath in DATASET_FILES:
        filename = os.path.basename(filepath)
        
        if filename in cached:
            cached_id = cached[filename]
            if verify_file_exists(cached_id):
                print(f"Using cached file ID for {filename}: {cached_id}")
                file_ids.append(cached_id)
                continue
            else:
                print(f"Cached file ID for {filename} expired, re-uploading...")
        
        if not os.path.exists(filepath):
            print(f"Warning: Dataset file not found: {filepath}")
            continue
            
        print(f"Uploading {filename} to OpenAI...")
        with open(filepath, 'rb') as f:
            response = client.files.create(
                file=f,
                purpose='assistants'
            )
        
        file_id = response.id
        print(f"Uploaded {filename} with file ID: {file_id}")
        file_ids.append(file_id)
        cached[filename] = file_id
        updated = True
    
    if updated:
        save_cached_file_ids(cached)
    
    return file_ids


# ============================================================================
# System Instructions
# ============================================================================

SYSTEM_INSTRUCTIONS = """You are The Fight Agent, an expert MMA handicapper and analyst AI assistant.

You have access to two comprehensive MMA datasets via code interpreter:
1. fighter_info.csv - Contains detailed fighter information including records, physical attributes, win streaks, recent performance, fighting styles, and career statistics.
2. event_data_sherdog.csv - Contains historical event and fight data from Sherdog.

Your capabilities:
- Analyze fighter matchups and provide detailed breakdowns
- Generate statistical visualizations (charts, graphs) using matplotlib, seaborn, or plotly
- Provide fight predictions with reasoning based on data
- Answer questions about fighter histories, records, and trends
- Create comparative analysis between fighters

Guidelines:
- Always use the data files to back up your analysis with real statistics
- When asked about fighters, look them up in the datasets
- Be concise but insightful - Twitter has character limits
- If generating visualizations, make them clear and informative
- Provide confident predictions but acknowledge uncertainty where appropriate
- If a fighter isn't in the database, say so rather than making up data

Response style:
- Be direct and confident like a professional sports analyst
- Use MMA terminology appropriately
- Keep responses Twitter-friendly (concise but substantive)
"""


# ============================================================================
# Response Processing with Responses API
# ============================================================================

def process_tweet_with_responses_api(tweet_text, file_ids):
    """
    Process a tweet using OpenAI's Responses API with Code Interpreter.
    
    Returns:
        tuple: (text_response, image_url or None)
    """
    tools = []
    if file_ids:
        tools.append({
            "type": "code_interpreter",
            "container": {
                "type": "auto",
                "file_ids": file_ids
            }
        })
    
    # Model options: "gpt-5-mini" (balanced), "gpt-5-nano" (cheapest), "gpt-4.1-mini" (fallback)
    response = client.responses.create(
        model="gpt-5-mini",
        instructions=SYSTEM_INSTRUCTIONS,
        input=[
            {
                "role": "user",
                "content": tweet_text
            }
        ],
        tools=tools if tools else None,
        temperature=0.7,
        max_output_tokens=1000
    )
    
    text_response = None
    image_url = None
    
    for output_item in response.output:
        if output_item.type == "message":
            for content_block in output_item.content:
                if hasattr(content_block, 'text'):
                    text_response = content_block.text
                    break
        elif output_item.type == "code_interpreter_call":
            if output_item.outputs:
                for output in output_item.outputs:
                    if output.type == "image":
                        image_url = output.url
                        break
    
    return text_response, image_url


# ============================================================================
# Main Processing Logic
# ============================================================================

# Upload datasets
print("\nPreparing datasets for Code Interpreter...")
file_ids = upload_datasets()
if file_ids:
    print(f"Ready with {len(file_ids)} dataset file(s)")
else:
    print("Warning: No dataset files available.")

# Load processed tweet IDs
processed_ids = set()
try:
    with open('data/processed_tweet_ids.txt', 'r') as f:
        processed_ids = {line.strip() for line in f if line.strip()}
except FileNotFoundError:
    print("No previous tweet ID log found, starting fresh")

# Load tweets from document
tweets_file = 'data/TheFightAgentMentions.docx'
if not os.path.exists(tweets_file):
    print(f"Tweets file not found: {tweets_file}")
    exit()

document = Document(tweets_file)
tweets = []
tweet_data = {}
temp_tweet = None

for paragraph in document.paragraphs:
    text = paragraph.text.strip()
    if text.startswith('-----------------------------------'):
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

# Process each tweet
for tweet in tweets:
    print(f"\nTweet: {tweet}")
    tweet_id = tweet_data[tweet]
    
    try:
        # Generate new response using Responses API
        print("Processing with Responses API...")
        ai_response, image_url = process_tweet_with_responses_api(tweet, file_ids)
        
        if not ai_response:
            print("No valid AI response found.")
            continue
            
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
        
        # Upload response and reply on Twitter
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
            with open('data/processed_tweet_ids.txt', 'a') as f:
                f.write(f"{tweet_id}\n")
            print(f"Logged processed tweet ID: {tweet_id}")
            
    except Exception as e:
        print(f"Error processing tweet: {e}")
        import traceback
        traceback.print_exc()
        continue
    
    time.sleep(5)
