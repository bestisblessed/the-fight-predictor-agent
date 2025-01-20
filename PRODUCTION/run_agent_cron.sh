#!/bin/bash

# */5 * * * * /home/trinity/the-fight-predictor-agent/PRODUCTION/run_agent_cron.sh >> /home/trinity/the-fight-predictor-agent/PRODUCTION/cron.log 2>&1

# export HOME=/home/trinity
echo $HOME
# echo "HOME is set to: $HOME" >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log 2>&1
# env >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log 2>&1

touch $HOME/the-fight-predictor-agent/PRODUCTION/cron.log
# echo "------------------------------------------------" >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log
echo "Starting Agent: $(date)" >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log

cd $HOME/the-fight-predictor-agent/PRODUCTION
# $HOME/.pyenv/shims/python download_mentions_from_drive.py
# $HOME/.pyenv/shims/python assistant_from_tweets.py
# $HOME/.pyenv/shims/python download_mentions_from_drive.py >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log 2>&1
# $HOME/.pyenv/shims/python assistant_from_tweets.py >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log 2>&1
$HOME/.pyenv/shims/python $HOME/the-fight-predictor-agent/PRODUCTION/download_mentions_from_drive.py >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log 2>&1
$HOME/.pyenv/shims/python $HOME/the-fight-predictor-agent/PRODUCTION/assistant_from_tweets.py >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log 2>&1


echo "Completed Agent: $(date)" >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log
echo "------------------------------------------------" >> $HOME/the-fight-predictor-agent/PRODUCTION/cron.log
