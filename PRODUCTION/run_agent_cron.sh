#!/bin/bash

touch $HOME/the-fight-predictor-agent/PRODUCTION/cron.log
echo "=== Starting Fight Predictor Agent at $(date) ===" >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log

cd $HOME/the-fight-predictor-agent/PRODUCTION
$HOME/.pyenv/shims/python download_mentions_from_drive.py
$HOME/.pyenv/shims/python assistant_from_tweets.py

echo "=== Completed Fight Predictor Agent at $(date) ===" >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log
