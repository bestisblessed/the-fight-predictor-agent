#!/bin/bash

set -euo pipefail

# */5 * * * * /home/trinity/the-fight-predictor-agent/PRODUCTION/run_agent_cron.sh >> /home/trinity/the-fight-predictor-agent/PRODUCTION/cron.log 2>&1

# export HOME=/home/trinity
# echo $HOME
# echo "HOME is set to: $HOME" >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log 2>&1
# env >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log 2>&1
LOG_FILE="$HOME/the-fight-predictor-agent/PRODUCTION/cron.log"

touch "$LOG_FILE"
echo "Starting Agent: $(date)" >> "$LOG_FILE"

cd "$HOME/the-fight-predictor-agent/PRODUCTION"
# $HOME/.pyenv/shims/python download_mentions_from_drive.py
# $HOME/.pyenv/shims/python assistant_from_tweets.py
# $HOME/.pyenv/shims/python download_mentions_from_drive.py >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log 2>&1
# $HOME/.pyenv/shims/python assistant_from_tweets.py >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log 2>&1
#$HOME/.pyenv/shims/python $HOME/the-fight-predictor-agent/PRODUCTION/download_mentions_from_drive.py >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log 2>&1
"$HOME/.pyenv/shims/python" "$HOME/the-fight-predictor-agent/PRODUCTION/download_mentions_from_drive_service_account.py" >> "$LOG_FILE" 2>&1
"$HOME/.pyenv/shims/python" "$HOME/the-fight-predictor-agent/PRODUCTION/assistant_from_tweets.py" >> "$LOG_FILE" 2>&1


echo "HEALTHCHECK_OK: fight-predictor-agent" >> "$LOG_FILE"
echo "Completed Agent: $(date)" >> "$LOG_FILE"
echo "------------------------------------------------" >> "$LOG_FILE"
echo "------------------------------------------------" >> "$LOG_FILE"
echo "------------------------------------------------" >> "$LOG_FILE"
