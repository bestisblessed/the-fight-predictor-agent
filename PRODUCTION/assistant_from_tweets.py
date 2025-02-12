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
os.makedirs('responses', exist_ok=True)
os.makedirs('files', exist_ok=True)
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

print(f"\nFound new tweets: {len(tweets)}")

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
    print(f"Run created with ID: {run.id}")
    print("Processing...")
    while run.status != "completed":
        time.sleep(2)
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
    messages = client.beta.threads.messages.list(thread_id=thread_id)

    tweet_id = tweet_data[tweet]
    # ai_response = None

    # # ai_response_text = None  # Initialize ai_response_text variable before processing messages
    # # ai_response_image = None  # Initialize ai_response_image variable
    # # ai_response = None

    # # First pass: gather the AI's text (if any)
    # for msg in messages.data:
    #     if msg.role != "user" and hasattr(msg.content[0], "text"):
    #         # Capture the assistant's text
    #         ai_response = msg.content[0].text.value
    #         print(f"AI Text: {ai_response}")

    #         # Save the AI text response immediately
    #         os.makedirs('responses', exist_ok=True)
    #         response_file = f"responses/{tweet_id}.txt"
    #         with open(response_file, 'a', encoding='utf-8') as f:
    #             f.write(ai_response + "\n\n")
    #         print(f"Appended AI text: {ai_response}")

    #         # Since we've found the most recent text from the assistant, break out
    #         break
    # Initialize ai_response to None
    ai_response = None

    # Iterate over each message in the data
    for msg in messages.data:
        # Check if the message is from the assistant and has content
        if msg.role == "assistant" and hasattr(msg, "content"):
            # Iterate over each content block in the message
            for content_block in msg.content:
                # Check if the content block is of type 'text' and has a 'text' attribute
                if content_block.type == "text" and hasattr(content_block, "text"):
                    # Extract the text value
                    ai_response = content_block.text.value.strip()
                    print(f"Extracted AI Response: {ai_response}")
                    break  # Exit the loop after finding the first valid response
            if ai_response:
                break  # Exit the outer loop if a response has been found

    # Handle the case where no valid AI response was found
    if not ai_response:
        print("No valid AI response found in messages.")

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

    # Second pass: handle any images
    for msg in reversed(messages.data):
        if msg.role != "user" and hasattr(msg.content[0], "image_file"):
            print("AI: [Image file received]")
            file_id = msg.content[0].image_file.file_id
            file_url = f"https://api.openai.com/v1/files/{file_id}/content"
            headers = {"Authorization": f"Bearer {openai.api_key}"}
            print("Downloading image...")
            image_data = requests.get(file_url, headers=headers)
            if image_data.status_code == 200:
                image_path = f"files/{tweet_id}.png"
                with open(image_path, "wb") as imgf:
                    imgf.write(image_data.content)
                print(f"Image saved to {image_path}")
            else:
                print("Failed to download the image.")
        else:
            print("AI: [Unsupported content type or user message]")

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
    with open('data/processed_tweet_ids.txt', 'a') as f:
        f.write(f"{tweet_id}")
        f.write("")  # Platform-independent newline
        f.write("\n")  # Platform-independent newline
        # f.write(f"{tweet_id}\n")
    print(f"Logged processed tweet ID: {tweet_id}")


