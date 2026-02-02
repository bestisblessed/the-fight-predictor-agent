"""
MMA AI Agent - Twitter Mention Responder
Migrated from OpenAI Assistants API to Responses API with Code Interpreter

This script processes tweets from a document, sends them to OpenAI's Responses API
with Code Interpreter capability (with MMA datasets attached), and replies via Twitter.
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

# Paths to the MMA datasets (relative to PRODUCTION folder)
DATASET_FILES = [
    'data/fighter_info.csv',
    'data/event_data_sherdog.csv'
]

# File to store uploaded file IDs (so we don't re-upload every time)
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
    """
    Upload MMA datasets to OpenAI for use with Code Interpreter.
    Returns a list of file IDs.
    """
    cached = load_cached_file_ids()
    file_ids = []
    updated = False
    
    for filepath in DATASET_FILES:
        filename = os.path.basename(filepath)
        
        # Check if we have a cached file ID that's still valid
        if filename in cached:
            cached_id = cached[filename]
            if verify_file_exists(cached_id):
                print(f"Using cached file ID for {filename}: {cached_id}")
                file_ids.append(cached_id)
                continue
            else:
                print(f"Cached file ID for {filename} is no longer valid, re-uploading...")
        
        # Upload the file
        if not os.path.exists(filepath):
            print(f"Warning: Dataset file not found: {filepath}")
            continue
            
        print(f"Uploading {filename} to OpenAI...")
        with open(filepath, 'rb') as f:
            response = client.files.create(
                file=f,
                purpose='assistants'  # Used for code_interpreter/assistants
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
# System Instructions for the MMA AI Agent
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

MAX_OUTPUT_TOKENS = 7500


# ============================================================================
# Response Processing with Responses API
# ============================================================================

def process_tweet_with_responses_api(tweet_text, file_ids):
    """
    Process a tweet using OpenAI's Responses API with Code Interpreter.
    
    Args:
        tweet_text: The tweet content to process
        file_ids: List of uploaded file IDs for code interpreter
        
    Returns:
        tuple: (text_response, image_url or None)
    """
    # Build the code interpreter tool configuration
    tools = []
    if file_ids:
        tools.append({
            "type": "code_interpreter",
            "container": {
                "type": "auto",
                "file_ids": file_ids
            }
        })
    
    def extract_response_output(response):
        text_response = None
        image_url = None
        
        output_text = getattr(response, "output_text", None)
        if output_text:
            text_response = output_text
            print(f"Extracted text from output_text: {text_response[:100]}..." if len(text_response) > 100 else f"Extracted text: {text_response}")
        
        output_items = getattr(response, "output", None) or []
        print(f"Number of output items: {len(output_items)}")
        
        for i, output_item in enumerate(output_items):
            item_type = getattr(output_item, "type", None)
            print(f"Output item {i}: type={item_type}")
            
            # Handle text messages
            if item_type == "message":
                content_items = getattr(output_item, "content", None) or []
                for j, content_block in enumerate(content_items):
                    block_type = getattr(content_block, "type", None)
                    print(f"  Content block {j}: type={block_type}")
                    
                    if block_type == "output_text" and not text_response:
                        text_attr = getattr(content_block, "text", None)
                        if text_attr:
                            text_response = text_attr if isinstance(text_attr, str) else str(text_attr)
                            print(f"  Extracted text (output_text): {text_response[:100]}..." if len(text_response) > 100 else f"  Extracted text: {text_response}")
                            break
                    elif block_type == "output_message" and not text_response:
                        text_attr = getattr(content_block, "text", None)
                        if text_attr:
                            if isinstance(text_attr, str):
                                text_response = text_attr
                            elif hasattr(text_attr, "value"):
                                text_response = text_attr.value
                            else:
                                text_response = str(text_attr)
                            print(f"  Extracted text: {text_response[:100]}..." if len(text_response) > 100 else f"  Extracted text: {text_response}")
                            break
                
                if text_response:
                    break
            
            # Handle code interpreter outputs (for images and logs)
            elif item_type == "code_interpreter_call":
                output_list = getattr(output_item, "outputs", None) or []
                for output in output_list:
                    output_type = getattr(output, "type", None)
                    if output_type == "image":
                        image_url = getattr(output, "url", None)
                        if image_url:
                            print(f"  Found image URL: {image_url}")
                    elif output_type in {"text", "logs"} and not text_response:
                        text_attr = getattr(output, "text", None)
                        if text_attr:
                            text_response = text_attr if isinstance(text_attr, str) else str(text_attr)
                            print(f"  Extracted text from tool output: {text_response[:100]}..." if len(text_response) > 100 else f"  Extracted text: {text_response}")
        
        return text_response, image_url

    max_attempts = 2
    max_wait_seconds = 120
    poll_interval_seconds = 1
    terminal_statuses = {"completed", "cancelled", "failed", "incomplete"}
    max_output_tokens = MAX_OUTPUT_TOKENS

    def get_incomplete_reason(details):
        if not details:
            return None
        if isinstance(details, str):
            return details
        return getattr(details, "reason", None)

    for attempt in range(1, max_attempts + 1):
        try:
            # Create the response using the Responses API
            # Model options (non-pro, cost-effective):
            #   - "gpt-5-mini": Best balance of capability and cost for well-defined tasks
            #   - "gpt-5-nano": Fastest and cheapest, good for simple queries
            #   - "gpt-4.1-mini": Reliable fallback, non-reasoning model
            response = client.responses.create(
                model="gpt-5-mini",  # Recommended for MMA analysis tasks
                instructions=SYSTEM_INSTRUCTIONS,
                input=[
                    {
                        "role": "user",
                        "content": tweet_text
                    }
                ],
                tools=tools if tools else [],
                max_output_tokens=max_output_tokens,
                store=True
                # Note: temperature not supported by gpt-5-mini (reasoning model)
            )
            
            print(f"Response ID: {response.id}")
            print(f"Response status: {response.status}")
            
            # Poll until response reaches a terminal state
            start_time = time.time()
            timed_out = False
            while response.status not in terminal_statuses:
                if time.time() - start_time >= max_wait_seconds:
                    timed_out = True
                    print("Timed out waiting for response completion.")
                    break
                time.sleep(poll_interval_seconds)
                response = client.responses.retrieve(response.id)
                print(f"Response status: {response.status}")
            
            if response.status != "completed":
                print(f"Final response status: {response.status}")
                if response.status == "incomplete":
                    incomplete_details = getattr(response, "incomplete_details", None)
                    incomplete_reason = get_incomplete_reason(incomplete_details)
                    if incomplete_details:
                        print(f"Response incomplete details: {incomplete_details}")
                    if incomplete_reason == "max_output_tokens" and attempt < max_attempts:
                        max_output_tokens = min(max_output_tokens * 2, 6000)
                        print(f"Increasing max_output_tokens to {max_output_tokens} for retry.")
            
            text_response, image_url = extract_response_output(response)
            if text_response or image_url:
                return text_response, image_url
            
            if timed_out and response.status in {"queued", "in_progress"}:
                try:
                    client.responses.cancel(response.id)
                    print("Cancelled timed out response.")
                except Exception as cancel_error:
                    print(f"Error cancelling timed out response: {cancel_error}")
            
            if attempt < max_attempts:
                print("No valid AI response. Retrying...")
        except Exception as e:
            print(f"Error in process_tweet_with_responses_api: {e}")
            import traceback
            traceback.print_exc()
            if attempt < max_attempts:
                print("Retrying after error...")
                continue
            return None, None

    return None, None


def download_image(image_url, save_path):
    """Download an image from a URL and save it locally."""
    try:
        response = requests.get(image_url, timeout=30)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            print(f"Image saved to {save_path}")
            return True
        else:
            print(f"Failed to download image. Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error downloading image: {e}")
        return False


# ============================================================================
# Main Processing Logic
# ============================================================================

# Upload datasets and get file IDs
print("\nPreparing datasets for Code Interpreter...")
file_ids = upload_datasets()
if file_ids:
    print(f"Ready with {len(file_ids)} dataset file(s)")
else:
    print("Warning: No dataset files available. Proceeding without code interpreter data.")

# Load processed tweet IDs to avoid reprocessing
processed_ids = set()
try:
    with open('data/processed_tweet_ids.txt', 'r') as f:
        processed_ids = {line.strip() for line in f if line.strip()}
except FileNotFoundError:
    print("No previous tweet ID log found, starting fresh")

# Path to the docx file containing tweets
tweets_file = 'data/TheFightAgentMentions.docx'

if not os.path.exists(tweets_file):
    print(f"Tweets file not found: {tweets_file}")
    exit()

document = Document(tweets_file)
tweets = []
tweet_data = {}  # Store both tweet text and ID together

# Gather tweets that haven't been processed yet
temp_tweet = None  # Store tweet text temporarily until we find its ID

for paragraph in document.paragraphs:
    text = paragraph.text.strip()
    if text.startswith('-----------------------------------'):
        temp_tweet = None  # Reset temporary tweet storage
    elif text.startswith('Tweet:'):
        temp_tweet = text.replace('Tweet:', '').strip()  # Store tweet text
    elif text.startswith('Link:'):
        current_id = text.split('/')[-1].strip()
        print(f"Found Link ID: {current_id}")
        # Now that we have both tweet and ID, check if we should process it
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
    print(f"\n{'='*60}")
    print(f"Processing Tweet: {tweet}")
    print('='*60)
    
    tweet_id = tweet_data[tweet]
    
    try:
        # Process the tweet using the Responses API
        ai_response, image_url = process_tweet_with_responses_api(tweet, file_ids)
        
        if ai_response:
            print(f"AI Response: {ai_response}")
        else:
            ai_response = "I encountered an issue analyzing this request. Please try again."
            print("No valid AI response received.")
        
        # Save AI response to file
        response_file = f"responses/{tweet_id}.txt"
        with open(response_file, 'w', encoding='utf-8') as f:
            f.write(ai_response)
        print(f"Response saved to {response_file}")
        
        # Handle image if generated
        if image_url:
            print(f"Image generated: {image_url}")
            image_path = f"files/{tweet_id}.png"
            download_image(image_url, image_path)
        
        # Send reply to Twitter
        try:
            result = subprocess.run(
                ["python", "reply_single_tweet.py", tweet_id, ai_response],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"Reply script output: {result.stdout}")
            print("Successfully sent reply to Twitter")
        except subprocess.CalledProcessError as e:
            print(f"Failed to send reply to Twitter. Error code: {e.returncode}")
            print(f"Error output: {e.stderr}")
            print(f"Standard output: {e.stdout}")
        
        # Log the processed tweet ID
        with open('data/processed_tweet_ids.txt', 'a') as f:
            f.write(f"{tweet_id}\n")
        print(f"Logged processed tweet ID: {tweet_id}")
        
    except Exception as e:
        print(f"Error processing tweet {tweet_id}: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*60)
print("Tweet processing complete.")
print("="*60)
