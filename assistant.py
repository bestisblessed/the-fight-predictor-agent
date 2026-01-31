"""
MMA AI Assistant - Interactive Chat Interface
Migrated from OpenAI Assistants API to Responses API with Code Interpreter

This script provides an interactive chat interface for testing the MMA AI agent.
"""

import openai
import time
import requests
import os
import json
from dotenv import load_dotenv
from PIL import Image
import io

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    print("API key is required to run the chatbot.")
    exit()

print("MMA AI Chatbot initialized (Responses API). Type 'exit' to quit.")

client = openai.OpenAI(api_key=openai.api_key)
os.makedirs('data', exist_ok=True)

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
- Provide thorough, detailed analysis for interactive queries
- If generating visualizations, make them clear and informative
- Provide confident predictions but acknowledge uncertainty where appropriate
- If a fighter isn't in the database, say so rather than making up data
"""


# ============================================================================
# Response Processing
# ============================================================================

def process_message(user_input, file_ids, conversation_id=None):
    """
    Process a user message using the Responses API.
    
    Args:
        user_input: The user's message
        file_ids: List of uploaded file IDs for code interpreter
        conversation_id: Optional previous response ID for conversation continuity
        
    Returns:
        tuple: (text_response, image_url, new_conversation_id)
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
    
    # Build request parameters
    # Model options (non-pro, cost-effective):
    #   - "gpt-5-mini": Best balance of capability and cost for well-defined tasks
    #   - "gpt-5-nano": Fastest and cheapest, good for simple queries  
    #   - "gpt-4.1-mini": Reliable fallback, non-reasoning model
    request_params = {
        "model": "gpt-5-mini",
        "instructions": SYSTEM_INSTRUCTIONS,
        "input": [
            {
                "role": "user",
                "content": user_input
            }
        ],
        "tools": tools if tools else None,
        "temperature": 0.7,
        "store": True  # Enable conversation storage
    }
    
    # Continue conversation if we have a previous response ID
    if conversation_id:
        request_params["previous_response_id"] = conversation_id
    
    response = client.responses.create(**request_params)
    
    # Parse the response
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
    
    return text_response, image_url, response.id


def download_and_display_image(image_url):
    """Download and display an image from a URL."""
    try:
        response = requests.get(image_url, timeout=30)
        if response.status_code == 200:
            filename = f"data/assistant_image_{int(time.time())}.png"
            with open(filename, "wb") as f:
                f.write(response.content)
            print(f"Image saved to {filename}")
            
            # Display the image
            img = Image.open(filename)
            img.show()
            return True
    except Exception as e:
        print(f"Error handling image: {e}")
    return False


# ============================================================================
# Main Interactive Loop
# ============================================================================

# Upload datasets
print("\nPreparing datasets for Code Interpreter...")
file_ids = upload_datasets()
if file_ids:
    print(f"Ready with {len(file_ids)} dataset file(s)\n")
else:
    print("Warning: No dataset files available. Proceeding without code interpreter data.\n")

conversation_id = None

while True:
    user_question = input("\nYOU: ")
    if user_question.lower() == 'exit':
        print("Exiting chatbot. Goodbye!")
        break
    
    if user_question.lower() == 'new':
        conversation_id = None
        print("Started a new conversation.")
        continue
    
    print("Processing...")
    
    try:
        text_response, image_url, conversation_id = process_message(
            user_question, file_ids, conversation_id
        )
        
        if text_response:
            print(f"\nAI: {text_response}")
        else:
            print("\nAI: [No text response received]")
        
        if image_url:
            print("\nAI: [Image generated]")
            download_and_display_image(image_url)
            
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
