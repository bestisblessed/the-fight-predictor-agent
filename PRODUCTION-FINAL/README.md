# PRODUCTION-FINAL

Polling-only production runtime for The Fight Agent on DonPablo.

This version does not run Flask, Gunicorn, Caddy, webhooks, tmux, screen, or an always-on worker. Cron runs one script, the script polls recent X mentions, replies to new unprocessed mentions, records state in `logs/`, and exits.

## Setup

```bash
cd /Users/pablo/Code/the-fight-predictor-agent/PRODUCTION-FINAL
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp ../OPTIMIZED-PYTHONANYWHERE/.env .env
```

## Verify

```bash
cd /Users/pablo/Code/the-fight-predictor-agent/PRODUCTION-FINAL
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -u poll_mentions.py --dry-run --limit 1 --max-results 5
```

`--dry-run` fetches mentions but does not reply and does not advance `logs/poll_state.json`.

## Cron

```cron
*/5 * * * * /Users/pablo/Code/polymarket-bots/opsdash-cron-run-m1 "Fight Predictor Agent" /Users/pablo/Code/the-fight-predictor-agent/PRODUCTION-FINAL/cron.log -- /Users/pablo/Code/the-fight-predictor-agent/PRODUCTION-FINAL/run_agent_m1_cron.sh
```

## Opsdash

Add this under `donpablo.cron_jobs` in `/Users/pablo/Code/my-bots-dashboard/opsdash.yaml`:

```yaml
- match: /Users/pablo/Code/the-fight-predictor-agent/PRODUCTION-FINAL/run_agent_m1_cron.sh
  name: Fight Predictor Agent
  last_run_files:
    - /Users/pablo/Code/the-fight-predictor-agent/PRODUCTION-FINAL/cron.log
```
