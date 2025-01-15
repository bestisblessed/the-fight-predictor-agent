#!/bin/bash

echo "=== Starting Fight Predictor Agent at $(date) ===" >> /home/trinity/the-fight-predictor-agent/cron.log

# Load environment variables
#if [ -f /home/trinity/the-fight-predictor-agent/.env ]; then
 #   export $(cat /home/trinity/the-fight-predictor-agent/.env | xargs)
 #   echo "Loaded environment variables" >> /home/trinity/the-fight-predictor-agent/cron.log
e#lse
 #   echo "ERROR: .env file not found" >> /home/trinity/the-fight-predictor-agent/cron.log
 #   exit 1
#fi

# Run with pyenv Python
cd /home/trinity/the-fight-predictor-agent
/home/trinity/.pyenv/shims/python X/download_mentions_from_drive.py
/home/trinity/.pyenv/shims/python assistant_from_tweets.py

echo "=== Completed Fight Predictor Agent at $(date) ===" >> /home/trinity/the-fight-predictor-agent/cron.log
