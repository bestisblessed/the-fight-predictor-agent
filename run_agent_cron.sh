#!/bin/bash

echo "=== Starting Fight Predictor Agent at $(date) ===" >> /home/trinity/the-fight-predictor-agent/cron.log

cd /home/trinity/the-fight-predictor-agent
/home/trinity/.pyenv/shims/python X/download_mentions_from_drive.py
/home/trinity/.pyenv/shims/python assistant_from_tweets.py

echo "=== Completed Fight Predictor Agent at $(date) ===" >> /home/trinity/the-fight-predictor-agent/cron.log
