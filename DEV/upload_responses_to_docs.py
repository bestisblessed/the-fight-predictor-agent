from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import sys

# Only need Docs API scope
SCOPES = ['https://www.googleapis.com/auth/documents']

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

def create_doc(file_path):
    creds = authenticate()
    docs_service = build('docs', 'v1', credentials=creds)

    # Read the content of the text file
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # Create a new Google Doc
    doc_metadata = {
        'title': os.path.splitext(os.path.basename(file_path))[0],
    }
    
    try:
        # Create the initial empty document
        doc = docs_service.documents().create(body=doc_metadata).execute()
        doc_id = doc.get('documentId')

        # Insert the content into the document
        requests = [{
            'insertText': {
                'location': {
                    'index': 1
                },
                'text': content
            }
        }]
        
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()

        print(f"Google Doc created successfully with ID: {doc_id}")
        return doc_id

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def main():
    # Get tweet ID from command line argument
    if len(sys.argv) != 2:
        print("Usage: python upload_responses_to_docs.py <tweet_id>")
        sys.exit(1)

    tweet_id = sys.argv[1]
    file_path = f'responses/{tweet_id}.txt'  # Path to the response file

    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    create_doc(file_path)

if __name__ == '__main__':
    main()