from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os
import sys

# Define the scope for accessing Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive']

def authenticate():
    creds = None
    token_path = 'credentials/token.json'

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        os.makedirs('credentials', exist_ok=True)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return creds

def upload_file(file_path, mime_type, folder_id=None):
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)

    file_metadata = {'name': os.path.basename(file_path)}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaFileUpload(file_path, mimetype=mime_type)

    try:
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        print(f"File '{file_path}' uploaded successfully with ID: {file.get('id')}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Get tweet ID from command line argument
if len(sys.argv) != 2:
    print("Usage: python upload_responses_to_drive.py <tweet_id>")
    sys.exit(1)

tweet_id = sys.argv[1]
folder_id = '1BJfW72ihcRyUlG8mg7XkU_Hs8AnEv-f4'  # Google Drive folder ID for IFTTT/Responses
file_path = f'responses/{tweet_id}.txt'  # Path to the response file
mime_type = 'text/plain'  # MIME type of the file

if not os.path.exists(file_path):
    print(f"Error: File not found: {file_path}")
    sys.exit(1)

upload_file(file_path, mime_type, folder_id)
