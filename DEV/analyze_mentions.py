import json
import os

# Path to the JSON file
json_file_path = 'data/mentions.json'

# Check if the JSON file exists and is not empty
if os.path.exists(json_file_path) and os.path.getsize(json_file_path) > 0:
    with open(json_file_path, 'r') as file:
        try:
            mentions_data = json.load(file)
        except json.JSONDecodeError:
            print("Error: The JSON file is not valid.")
            mentions_data = {}
else:
    print("Error: The JSON file is empty or does not exist.")
    mentions_data = {}

# Print each tweet's details in a formatted way if data is available
if 'data' in mentions_data:
    for tweet in mentions_data.get('data', []):
        print(f"Tweet ID: {tweet['id']}")
        print(f"Author ID: {tweet['author_id']}")
        print(f"Created At: {tweet['created_at']}")
        print(f"Text: {tweet['text']}")
        print("-" * 40)
else:
    print("No tweet data available to display.")