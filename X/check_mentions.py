"""
curl --request GET \
  --url https://api.twitter.com/2/users/your_user_id/mentions \
  --header 'Authorization: Bearer AAAAAAAAAAAAAAAAAAAAAGOdyAEAAAAAZi%2FYdJp6zJDs6ym%2FLSJKgSbffgY%3DCsSZC9Fyuk3ntbvbX0B572OEEo951pR2dQ1XQpI44LuV6i3Et2'
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()
bearer_token = os.getenv("BEARER_TOKEN")

url = "https://api.twitter.com/2/users/{id}/mentions"
headers = {"Authorization": f"Bearer {bearer_token}"}
response = requests.request("GET", url, headers=headers)
print(response.text)

