#!/bin/bash

echo "=== Starting Fight Predictor Agent at $(date) ===" >> /home/trinity/the-fight-predictor-agent/cron.log

cd /home/trinity/the-fight-predictor-agent
python X/download_mentions_from_drive.py
python assistant_from_tweets.py

echo "=== Completed Fight Predictor Agent at $(date) ===" >> /home/trinity/the-fight-predictor-agent/cron.log