# OPTIMIZED-PYTHONANYWHERE

Webhook-only X fight prediction agent. This replaces the cron + Google bridge flow with one always-on Flask service, local CSV-backed fighter context, OpenAI text generation, and direct X replies.

## What this version does

- Receives mentions through X Account Activity webhooks.
- Verifies CRC and `x-twitter-webhooks-signature`.
- Writes accepted events to `logs/events_inbox.jsonl`.
- Processes mentions in a single in-process background worker.
- Builds local context from `data/fighter_info.csv` and `data/event_data_sherdog.csv`, including typo and reversed-name matching.
- Generates one text reply with the OpenAI Responses API, with Code Interpreter and web search fallbacks when local matching is incomplete.
- Posts one direct reply through `POST /2/tweets`, then reposts that reply through `POST /2/users/:id/retweets`.

## What this version intentionally does not do

- No cron polling.
- No Google Drive, Google Docs, Google Sheets, or IFTTT.
- No database.
- No media replies or threads.
- No image generation.
- Code Interpreter is used only as a fallback resolver for ambiguous/missing local matches.
- Web search is used only after local matching and Code Interpreter cannot fully resolve the request.

## Files

- `app.py`: Flask webhook service with `/x/webhook` and `/healthz`.
- `admin.py`: setup and recovery CLI.
- `logs/`: runtime records and state files, including inbox events, processed IDs, replies, failures, checkpoints, webhook config, and OpenAI file cache.

## Local setup

```bash
cd /Users/td/Code/the-fight-predictor-agent/OPTIMIZED-PYTHONANYWHERE
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in the `.env` values before running anything.

## Local run

```bash
cd /Users/td/Code/the-fight-predictor-agent/OPTIMIZED-PYTHONANYWHERE
source .venv/bin/activate
python app.py
```

The dev server binds to `127.0.0.1:8080`.

## Temporary HTTPS testing

X requires a public HTTPS webhook URL with no explicit port in the registered URL. For non-production testing, put the local Flask service behind a temporary HTTPS tunnel such as `ngrok` or `cloudflared`, then set:

```bash
PUBLIC_BASE_URL=https://your-tunnel-hostname.example
```

## First-run admin flow

Run these from `OPTIMIZED-PYTHONANYWHERE/` after the service is reachable over HTTPS:

```bash
python admin.py resolve-bot-user
python admin.py create-webhook
python admin.py validate-webhook
python admin.py subscribe
python admin.py check-subscription
python admin.py list-subscriptions
```

`subscribe` prefers `X_OAUTH2_USER_TOKEN` when present. If you leave that blank, it falls back to OAuth1a with your existing access token and access token secret.

## Replay and retry

To ask X for a replay window:

```bash
python admin.py replay --from-date 202604231300 --to-date 202604231330
```

To retry locally failed retryable jobs:

```bash
python admin.py retry-failed
```

## PythonAnywhere

Based on your dashboard screenshot, the current account appears to have roughly `2,000` CPU-seconds/day and `1.0 GB` of storage. That is enough for a low-volume webhook-driven fight agent if you keep it text-only, keep logs small, and avoid unnecessary background work.

The safe PythonAnywhere shape is:

- Web app: receive webhook requests and write `events_inbox.jsonl`
- Always-on task: run the worker loop and process new inbox records

Do not rely on the in-process worker thread inside the web app on PythonAnywhere. Use the dedicated worker script instead.

### PythonAnywhere setup steps

1. Upload or clone the repo into `/home/bestisblessed/the-fight-predictor-agent`
2. Open a Bash console and create the venv:

```bash
cd /home/bestisblessed/the-fight-predictor-agent/OPTIMIZED-PYTHONANYWHERE
python3.13 -m venv .venv
source .venv/bin/activate
pip install --no-cache-dir -r requirements.txt
```

3. Create `.env` from `.env.example`
4. On the **Web** tab:
   - create a new Flask web app with manual configuration
   - point the virtualenv at `/home/bestisblessed/the-fight-predictor-agent/OPTIMIZED-PYTHONANYWHERE/.venv`
   - edit the WSGI file so it imports `pythonanywhere_wsgi.py`
5. In the WSGI file, use:

```python
import sys
path = "/home/bestisblessed/the-fight-predictor-agent/OPTIMIZED-PYTHONANYWHERE"
if path not in sys.path:
    sys.path.insert(0, path)

from pythonanywhere_wsgi import application
```

6. On the **Tasks** page, create one always-on task with:

```bash
bash -lc 'cd ~/the-fight-predictor-agent/OPTIMIZED-PYTHONANYWHERE && .venv/bin/python -u pythonanywhere_worker.py'
```

Useful app files for missed-reply checks:

```bash
cd /home/bestisblessed/the-fight-predictor-agent/OPTIMIZED-PYTHONANYWHERE
tail -n 20 logs/events_inbox.jsonl
tail -n 20 logs/processed_event_ids.jsonl
tail -n 20 logs/replies.jsonl
tail -n 20 logs/failed_jobs.jsonl
cat logs/worker_checkpoint.json
```

7. Reload the web app, then run:

```bash
cd /home/bestisblessed/the-fight-predictor-agent/OPTIMIZED-PYTHONANYWHERE
source .venv/bin/activate
python admin.py resolve-bot-user
python admin.py create-webhook
python admin.py validate-webhook
python admin.py subscribe
```

Recommended production OpenAI settings:

```bash
OPENAI_MODEL=gpt-5.4-mini
OPENAI_TIMEOUT_SECONDS=90
# Optional higher-cost escalation model:
# OPENAI_ESCALATION_MODEL=gpt-5.5
```

### PythonAnywhere storage and CPU notes

- `1.0 GB` disk is tight but workable for this app. Use `--no-cache-dir` when installing dependencies and keep `logs/` files trimmed.
- On PythonAnywhere, CPU-seconds apply to consoles, scheduled tasks, and always-on tasks. They do not apply to normal web requests.
- A low-volume mention workflow should fit comfortably because the web app only handles short webhook requests and the always-on task mostly sleeps between short inbox scans.
- If mentions spike or the worker repeatedly scans a very large inbox, you can hit the tarpit and the always-on task will pause until your CPU allowance resets.
