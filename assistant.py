import os

import openai
from dotenv import load_dotenv
from PIL import Image

from responses_api_utils import (
    IMAGE_EXTENSIONS,
    create_response,
    default_cache_path,
    extract_file_entries,
    extract_text,
    get_dataset_file_ids,
    get_response_id,
    save_response_files,
    unique_filename_prefix,
)

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    print("API key is required to run the chatbot.")
    exit()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SYSTEM_PROMPT = os.getenv("OPENAI_SYSTEM_PROMPT")
DATA_DIR = os.getenv("DATA_DIR", "data")

print("MMA AI Chatbot initialized. Type 'exit' to quit.")

client = openai.OpenAI(api_key=openai.api_key)
os.makedirs(DATA_DIR, exist_ok=True)

try:
    dataset_file_ids = get_dataset_file_ids(
        client,
        data_dir=DATA_DIR,
        cache_path=default_cache_path(DATA_DIR),
    )
except FileNotFoundError as exc:
    print(str(exc))
    exit()

previous_response_id = None

while True:
    user_question = input("\nYOU: ")
    if user_question.lower() == "exit":
        print("Exiting chatbot. Goodbye!")
        break

    response = create_response(
        client,
        MODEL,
        user_question,
        dataset_file_ids,
        system_prompt=SYSTEM_PROMPT,
        previous_response_id=previous_response_id,
    )

    response_id = get_response_id(response)
    if response_id:
        previous_response_id = response_id

    ai_text = extract_text(response)
    if ai_text:
        print(f"AI: {ai_text}")
    else:
        print("AI: [No text response returned]")

    file_entries = extract_file_entries(response)
    if file_entries:
        prefix = unique_filename_prefix("assistant_output")
        saved_files = save_response_files(
            client,
            file_entries,
            DATA_DIR,
            prefix,
            api_key=openai.api_key,
        )
        for path in saved_files:
            print(f"File saved: {path}")
            ext = os.path.splitext(path)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                img = Image.open(path)
                img.show()
