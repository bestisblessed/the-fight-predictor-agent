#!/bin/bash

#python download_mentions_from_drive.py
python download_mentions_from_drive_service_account.py
# cp data/TheFightAgentMentions.docx data/TheFightAgentMentionsWorking.docx
python assistant_from_tweets.py
