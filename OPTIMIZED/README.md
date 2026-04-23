# OPTIMIZED

Webhook-only X fight prediction agent. This replaces the cron + Google bridge flow with one always-on Flask service, local CSV-backed fighter context, OpenAI text generation, and direct X replies.

## What this version does

- Receives mentions through X Account Activity webhooks.
- Verifies CRC and `x-twitter-webhooks-signature`.
- Writes accepted events to `state/events_inbox.jsonl`.
- Processes mentions in a single in-process background worker.
- Builds local context from `data/fighter_info.csv` and `data/event_data_sherdog.csv`.
- Generates one text reply with the OpenAI Responses API.
- Posts one direct reply through `POST /2/tweets`.

## What this version intentionally does not do

- No cron polling.
- No Google Drive, Google Docs, Google Sheets, or IFTTT.
- No database.
- No media replies, retweets, or threads.
- No Code Interpreter or image generation.

## Files

- `app.py`: Flask webhook service with `/x/webhook` and `/healthz`.
- `admin.py`: setup and recovery CLI.
- `state/`: file-backed state, retries, dedupe, and reply logs.
- `systemd/`: systemd service unit.
- `nginx/`: Nginx reverse-proxy example.

## Local setup

```bash
cd /Users/td/Code/the-fight-predictor-agent/OPTIMIZED
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in the `.env` values before running anything.

## Local smoke test

```bash
cd /Users/td/Code/the-fight-predictor-agent/OPTIMIZED
source .venv/bin/activate
python -m unittest discover -s tests -v
python app.py
```

The dev server binds to `127.0.0.1:8080`.

## Temporary HTTPS testing

X requires a public HTTPS webhook URL with no explicit port in the registered URL. For non-production testing, put the local Flask service behind a temporary HTTPS tunnel such as `ngrok` or `cloudflared`, then set:

```bash
PUBLIC_BASE_URL=https://your-tunnel-hostname.example
```

## First-run admin flow

Run these from `OPTIMIZED/` after the service is reachable over HTTPS:

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

## Production deployment on the current server

### 1. Create the venv and install dependencies

```bash
cd /home/trinity/the-fight-predictor-agent/OPTIMIZED
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Add the environment file

Create `/home/trinity/the-fight-predictor-agent/OPTIMIZED/.env` from `.env.example`.

### 3. Install the systemd unit

Copy `systemd/fight-agent-optimized.service` to `/etc/systemd/system/`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable fight-agent-optimized
sudo systemctl start fight-agent-optimized
sudo systemctl status fight-agent-optimized
```

### 4. Install the Nginx site

Copy `nginx/fight-agent-optimized.conf` to `/etc/nginx/sites-available/`, update `server_name`, then enable it with your normal Nginx site workflow.

### 5. Add TLS

After DNS points to the server and Nginx is serving the hostname, use Certbot for the hostname you set in `PUBLIC_BASE_URL`.

### 6. Verify the service

```bash
curl https://your-hostname.example/healthz
python admin.py create-webhook
python admin.py validate-webhook
python admin.py subscribe
```

## Gunicorn

Run a single worker only. The runtime is intentionally single-process so the in-memory queue and file-backed dedupe stay coherent.

Example:

```bash
cd /home/trinity/the-fight-predictor-agent/OPTIMIZED
source .venv/bin/activate
gunicorn --workers 1 --bind 127.0.0.1:8080 app:create_app\(\)
```

## PythonAnywhere

Based on your dashboard screenshot, the current account appears to have roughly `2,000` CPU-seconds/day and `1.0 GB` of storage. That is enough for a low-volume webhook-driven fight agent if you keep it text-only, keep logs small, and avoid unnecessary background work.

The safe PythonAnywhere shape is:

- Web app: receive webhook requests and write `events_inbox.jsonl`
- Always-on task: run the worker loop and process new inbox records

Do not rely on the in-process worker thread inside the web app on PythonAnywhere. Use the dedicated worker script instead.
Do not use the `systemd/` or `nginx/` assets on PythonAnywhere; their web app + WSGI stack replaces that part.

### PythonAnywhere setup steps

1. Upload or clone the repo into `/home/bestisblessed/the-fight-predictor-agent`
2. Open a Bash console and create the venv:

```bash
cd /home/bestisblessed/the-fight-predictor-agent/OPTIMIZED
python3.13 -m venv .venv
source .venv/bin/activate
pip install --no-cache-dir -r requirements.txt
```

3. Create `.env` from `.env.example`
4. On the **Web** tab:
   - create a new Flask web app with manual configuration
   - point the virtualenv at `/home/bestisblessed/the-fight-predictor-agent/OPTIMIZED/.venv`
   - edit the WSGI file so it imports `pythonanywhere_wsgi.py`
5. In the WSGI file, use:

```python
import sys
path = "/home/bestisblessed/the-fight-predictor-agent/OPTIMIZED"
if path not in sys.path:
    sys.path.insert(0, path)

from pythonanywhere_wsgi import application
```

6. On the **Tasks** page, create one always-on task with:

```bash
source /home/bestisblessed/the-fight-predictor-agent/OPTIMIZED/.venv/bin/activate && python -u /home/bestisblessed/the-fight-predictor-agent/OPTIMIZED/pythonanywhere_worker.py
```

7. Reload the web app, then run:

```bash
cd /home/bestisblessed/the-fight-predictor-agent/OPTIMIZED
source .venv/bin/activate
python admin.py resolve-bot-user
python admin.py create-webhook
python admin.py validate-webhook
python admin.py subscribe
```

### PythonAnywhere storage and CPU notes

- `1.0 GB` disk is tight but workable for this app. Use `--no-cache-dir` when installing dependencies and keep `state/` files trimmed.
- On PythonAnywhere, CPU-seconds apply to consoles, scheduled tasks, and always-on tasks. They do not apply to normal web requests.
- A low-volume mention workflow should fit comfortably because the web app only handles short webhook requests and the always-on task mostly sleeps between short inbox scans.
- If mentions spike or the worker repeatedly scans a very large inbox, you can hit the tarpit and the always-on task will pause until your CPU allowance resets.
