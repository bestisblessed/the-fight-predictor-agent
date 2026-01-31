import os
import subprocess
import sys
import time
from pathlib import Path

import openai
from dotenv import load_dotenv
from docx import Document

sys.path.append(str(Path(__file__).resolve().parents[1]))

from responses_api_utils import (
    create_response,
    default_cache_path,
    extract_file_entries,
    extract_text,
    get_dataset_file_ids,
    save_response_image,
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
# tweets_file = 'data/TheFightAgentMentionsCombined.docx'
document = Document(tweets_file)
tweets = []
tweet_data = {}  # Store both tweet text and ID together

# After initial imports and before processing tweets, load processed IDs
processed_ids_file = os.path.join(DATA_DIR, "processed_tweet_ids.txt")
processed_ids = set()
try:
    with open(processed_ids_file, "r") as f:
        processed_ids = {line.strip() for line in f if line.strip()}
    # print(f"Loaded {len(processed_ids)} processed tweet IDs")
except FileNotFoundError:
    print("No previous tweet ID log found, starting fresh")

# print(f"\nDebug: Loaded processed IDs: {processed_ids}")

# Path to the docx file containing tweets
tweets_file = os.path.join(DATA_DIR, "TheFightAgentMentions.docx")
# tweets_file = 'data/TheFightAgentMentionsCombined.docx'
document = Document(tweets_file)
tweets = []
tweet_data = {}  # Store both tweet text and ID together

# Gather tweets that haven't been processed yet
current_tweet = None
current_id = None
temp_tweet = None  # Store tweet text temporarily until we find its ID

for paragraph in document.paragraphs:
    text = paragraph.text.strip()
    if text.startswith('-----------------------------------'):
        current_id = None
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
    
    response = create_response(
        client,
        MODEL,
        tweet,
        dataset_file_ids,
        system_prompt=SYSTEM_PROMPT,
    )
    print("Processing...")

    tweet_id = tweet_data[tweet]

    ai_response = extract_text(response)
    if not ai_response:
        print("No valid AI response found in response output.")
        continue

    print(f"Extracted AI Response: {ai_response}")
    file_entries = extract_file_entries(response)

    # Save AI response to file
    response_file = f"responses/{tweet_data[tweet]}.txt"
    with open(response_file, 'w', encoding='utf-8') as f:
        f.write(ai_response)


    # # If nothing found, default to a message
    # if ai_response is None:
    #     ai_response = "No text response received from AI."
    #     # Still save a file if you want to ensure it always exists:
    #     os.makedirs('responses', exist_ok=True)
    #     response_file = f"responses/{tweet_id}.txt"
    #     with open(response_file, 'w', encoding='utf-8') as f:
    #         f.write(ai_response)
    #     print(f"Saved default text response to {response_file}")

    # Save output image if returned
    if file_entries:
        image_path = f"files/{tweet_id}.png"
        saved_image = save_response_image(
            client,
            file_entries,
            image_path,
            api_key=openai.api_key,
        )
        if saved_image:
            print(f"Image saved to {saved_image}")

    # Always run the reply script with the text response
    try:
        result = subprocess.run(
            ["python", "reply_single_tweet.py", tweet_id, ai_response],
            # [
            #     "python",
            #     "reply_single_tweet.py",
            #     str(tweet_id),       # Ensure it's a string
            #     str(ai_response)     # Ensure it's a string
            # ],
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
    with open(processed_ids_file, "a") as f:
        f.write(f"{tweet_id}")
        f.write("")  # Platform-independent newline
        f.write("\n")  # Platform-independent newline
        # f.write(f"{tweet_id}\n")
    print(f"Logged processed tweet ID: {tweet_id}")


