import requests
import os
from dotenv import load_dotenv
import time
load_dotenv()
bearer_token = os.getenv("BEARER_TOKEN")
if not bearer_token:
    print("Error: Bearer Token not found. Please check your .env file.")
else:
    url = "https://api.twitter.com/2/users/by/username/TheFightAgent"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        rate_limit_remaining = response.headers.get("x-rate-limit-remaining")
        rate_limit_reset = response.headers.get("x-rate-limit-reset")
        print(f"Rate Limit Remaining: {rate_limit_remaining} requests")
        if rate_limit_reset:
            reset_time = time.strftime('%Y-%m-%d %I:%M:%S %p', time.localtime(int(rate_limit_reset)))
            print(f"Rate Limit Resets At: {reset_time} (local time)")
    else:
        print(f"Error: {response.status_code}, {response.text}")