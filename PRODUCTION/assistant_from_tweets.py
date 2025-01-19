import openai
import time
import requests
import os
from dotenv import load_dotenv
from PIL import Image
import io
from docx import Document
import subprocess
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
assistant_mma_handicapper = 'asst_zahT75OFBs5jgi346C9vuzKa' 
if not openai.api_key:
    print("API key is required to run the chatbot.")
    exit()
print("MMA AI Chatbot Initialized - Processing Tweets.")
client = openai.OpenAI(api_key=openai.api_key)
os.makedirs('data', exist_ok=True)
thread_id = None
tweets_file = 'data/TheFightAgentMentions.docx'
# tweets_file = 'data/TheFightAgentMentionsCombined.docx'
document = Document(tweets_file)
tweets = []
tweet_data = {}  # Store both tweet text and ID together

# After initial imports and before processing tweets, load processed IDs
processed_ids = set()
try:
    with open('data/processed_tweet_ids.txt', 'r') as f:
        processed_ids = {line.strip() for line in f if line.strip()}
    # print(f"Loaded {len(processed_ids)} processed tweet IDs")
except FileNotFoundError:
    print("No previous tweet ID log found, starting fresh")

# print(f"\nDebug: Loaded processed IDs: {processed_ids}")

# Path to the docx file containing tweets
tweets_file = 'data/TheFightAgentMentions.docx'
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

# print(f"\nFound new tweets: {len(tweets)}")

if not tweets:
    print("No new tweets found to process.")
    exit()

print(f"Found {len(tweets)} new tweets to process.")

for tweet in tweets:
    print(f"\nTweet: {tweet}")
    
    # Create a new thread for each tweet
    thread = client.beta.threads.create()
    thread_id = thread.id
    print(f"New conversation started with Thread ID: {thread_id}")

    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=tweet
    )

    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_mma_handicapper
    )
    print("Processing...")
    while run.status != "completed":
        time.sleep(2)
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    for message in reversed(messages.data):
        if hasattr(message.content[0], 'text'):
            ai_response = message.content[0].text.value
            # Skip if this is the user's original question
            if message.role == "user":
                continue
            print(f"AI: {ai_response}")
            tweet_id = tweet_data[tweet]
            
            # Call the reply script as a subprocess with enhanced error handling
            try:
                result = subprocess.run(
                    ['python', 'reply_single_tweet.py', tweet_id, ai_response], 
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
                # Optionally, don't mark as processed if the reply failed
                continue

        elif hasattr(message.content[0], 'image_file'):
            print("AI: [Image file received]")
            file_id = message.content[0].image_file.file_id
            file_url = f"https://api.openai.com/v1/files/{file_id}/content"
            headers = {"Authorization": f"Bearer {openai.api_key}"}
            print("Downloading image...")
            image_data = requests.get(file_url, headers=headers)
            if image_data.status_code == 200:
                filename = f"data/assistant_image_{int(time.time())}.png"
                with open(filename, "wb") as f:
                    f.write(image_data.content)
                print(f"Image saved {filename}")
                img = Image.open(filename)
                img.show()  
            else:
                print("Failed to download the image.")
        else:
            print("AI: [Unsupported content type]")

    # After successful processing, just log the tweet ID
    tweet_id = tweet_data[tweet]  # Get the ID for this tweet
    
    # Save the raw AI response to a text file
    os.makedirs('responses', exist_ok=True)
    response_file = f'responses/{tweet_id}.txt'
    with open(response_file, 'w', encoding='utf-8') as f:
        f.write(ai_response)  # Just save the raw AI response
    print(f"Saved response to {response_file}")

    # Log the processed tweet ID
    with open('data/processed_tweet_ids.txt', 'a') as f:
        f.write(f"{tweet_id}")
        f.write("")  # Platform-independent newline
        f.write("\n")  # Platform-independent newline
        # f.write(f"{tweet_id}\n")
    print(f"Logged processed tweet ID: {tweet_id}")


