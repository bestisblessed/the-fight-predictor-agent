from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import os
import io

# Define the scope for accessing Google Drive
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive.file'
]

def authenticate():
    creds = None
    # Path to the token file
    token_path = 'credentials/token.json'
    
    # Load credentials from token file if it exists
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    # If no valid credentials are found, perform the OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Create credentials directory if it doesn't exist
        os.makedirs('credentials', exist_ok=True)
        
        # Save the credentials for future use
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    
    return creds

def export_file(file_id, file_name, mime_type):
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)
    try:
        request = service.files().export_media(fileId=file_id, mimeType=mime_type)
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        
        # Remove the file_path creation here since file_name already includes the path
        with io.FileIO(file_name, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                print(f"Download progress: {int(status.progress() * 100)}% | '{file_name}' downloaded successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")
        
# Replace 'file_id' and 'file_name' with your actual file ID and desired download name
file_id = '1YTd9zqq4lhNrZZXU4JJzbSgo-uUeuzcQq0oBYOS5lvk'
file_name = os.path.join('data', 'TheFightAgentMentions.docx')  # Add the correct extension and data directory
mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
export_file(file_id, file_name, mime_type)


# from google.oauth2.credentials import Credentials
# from google_auth_oauthlib.flow import InstalledAppFlow
# from googleapiclient.discovery import build
# from googleapiclient.http import MediaIoBaseDownload
# import io

# # Define the scope for accessing Google Drive
# SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# def authenticate():
#     flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
#     creds = flow.run_local_server(port=0)
#     return creds

# def export_file(file_id, file_name, mime_type):
#     creds = authenticate()
#     service = build('drive', 'v3', credentials=creds)
#     try:
#         request = service.files().export_media(fileId=file_id, mimeType=mime_type)
#         with io.FileIO(file_name, 'wb') as fh:
#             downloader = MediaIoBaseDownload(fh, request)
#             done = False
#             while not done:
#                 status, done = downloader.next_chunk()
#                 print(f"Download progress: {int(status.progress() * 100)}%")
#         print(f"File '{file_name}' exported and downloaded successfully.")
#     except Exception as e:
#         print(f"An error occurred: {e}")

# # Replace 'file_id' and 'file_name' with your actual file ID and desired download name
# file_id = '1LqOYgAPotW-cpqxF5sWnrT9FeIvbJo2dJyj2MMuy8-U'
# file_name = 'TheFightAgentMentions.docx'  # Add the correct extension
# mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'  # Change to desired export format
# export_file(file_id, file_name, mime_type)
