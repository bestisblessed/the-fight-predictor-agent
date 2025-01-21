from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os
import sys

# Define the scopes for accessing Google Drive and Sheets
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

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

def update_spreadsheet_cell(content, spreadsheet_id):
    creds = authenticate()
    sheets_service = build('sheets', 'v4', credentials=creds)

    try:
        # Update the content in cell A1
        range_name = 'Sheet1!A1'
        value_input_option = 'RAW'
        values = [[content]]  # 2D array for the cell
        body = {
            'values': values
        }

        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption=value_input_option,
            body=body
        ).execute()

        print(f"Cell updated successfully in spreadsheet: {spreadsheet_id}")
        print(f"View at: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Get tweet ID from command line argument
if len(sys.argv) != 2:
    print("Usage: python upload_responses_to_drive.py <tweet_id>")
    sys.exit(1)

tweet_id = sys.argv[1]
spreadsheet_id = '1ojtQSsgGk2hzBeSmxsv_Q1phgWzN0SQbwiKPFkkOYic'  # Replace with your actual spreadsheet ID
file_path = f'responses/{tweet_id}.txt'  # Path to the response file

if not os.path.exists(file_path):
    print(f"Error: File not found: {file_path}")
    sys.exit(1)

# Read the content from the text file
with open(file_path, 'r') as file:
    content = file.read()

update_spreadsheet_cell(content, spreadsheet_id)
