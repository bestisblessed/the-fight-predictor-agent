#!/usr/bin/env python3
"""
download_mentions_from_drive.py (Service Account Version)

This script uses a service account (credentials/service-account.json) to
export a Google Drive file (docx) into the data/ folder, bypassing
user-based OAuth flows and refresh tokens.
"""

import os
import io
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Define the scope for accessing Google Drive (read-only)
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Path to your service account JSON key
SERVICE_ACCOUNT_FILE = "credentials/service-account.json"


def authenticate():
    """
    Use a service account JSON to create drive credentials
    No refresh token or browser flow required.
    """
    # Create credentials object from service account file
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    return creds


def export_file(file_id, file_name, mime_type):
    """
    Export the specified Google Drive file (file_id) in the given mime_type
    and save it locally as file_name.
    """
    # 1) Authenticate with the service account
    creds = authenticate()

    # 2) Build the Drive service
    service = build('drive', 'v3', credentials=creds)

    try:
        # 3) Prepare an export media request
        request = service.files().export_media(
            fileId=file_id,
            mimeType=mime_type
        )

        # 4) Create the data directory if it doesn't exist
        os.makedirs(os.path.dirname(file_name), exist_ok=True)

        # 5) Download the exported file
        with io.FileIO(file_name, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    print(f"Download progress: {int(status.progress() * 100)}% | '{file_name}'")
        print(f"Successfully exported to '{file_name}'")
    except Exception as e:
        print(f"An error occurred: {e}")


# ----------------- MAIN EXECUTION EXAMPLE ------------------- #
# Reuse the same file_id, file_name, and MIME type from your original script
file_id = '1LExiqIf1oabiXtROiabHscZ0ywatB8u73FQ4vOA88Rw'  # from original script

file_name = os.path.join('data', 'TheFightAgentMentions.docx')
mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

export_file(file_id, file_name, mime_type)

