import requests
import os
from dotenv import load_dotenv
import json
from requests_oauthlib import OAuth1
from datetime import datetime, timezone
from pytz import timezone as pytz_timezone

# Load environment variables from .env file
load_dotenv()

url = "https://api.twitter.com/2/tweets"

# Payload for the tweet content
payload = json.dumps({
    "text": "Hello World!"
})

# OAuth 1.0a authentication setup
oauth = OAuth1(
    os.getenv('TWITTER_API_KEY'),
    os.getenv('TWITTER_API_SECRET'),
    os.getenv('TWITTER_ACCESS_TOKEN'),
    os.getenv('TWITTER_ACCESS_SECRET')
)

# Make the POST request to create a tweet
response = requests.post(url, auth=oauth, headers={"Content-Type": "application/json"}, data=payload)

# Print the response from the API
print("Status Code:", response.status_code)

# Extract and print key rate-limit details if available
headers = response.headers
if 'x-rate-limit-remaining' in headers and 'x-rate-limit-reset' in headers and 'x-app-limit-24hour-remaining' in headers:
    remaining_requests = headers['x-rate-limit-remaining']
    reset_time = headers['x-rate-limit-reset']
    app_remaining_requests = headers['x-app-limit-24hour-remaining']

    # print(f"Remaining Requests: {remaining_requests}")
    from datetime import datetime, timezone
    from pytz import timezone as pytz_timezone

    est = pytz_timezone('America/New_York')
    reset_time_est = datetime.fromtimestamp(int(reset_time), tz=timezone.utc).astimezone(est).strftime('%Y-%m-%d %I:%M:%S %p')
    print(f"Rate Limit Resets At (EST): {reset_time_est}")
    print(f"24-Hour App Limit Remaining: {app_remaining_requests}")
else:
    print("Rate limit details not available in response headers.")

print("Response Body:", response.json())
