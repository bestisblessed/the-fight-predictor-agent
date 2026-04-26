# OPTIMIZED-PYTHONANYWHERE Agent Handoff

## Scripts And Files

- `.env.example`: Template for required OpenAI, X, bot username, public URL, timeout, and reply-limit settings. Production uses a real `.env` file that is not committed.
- `README.md`: Human deployment guide for local testing, server deployment, and PythonAnywhere setup.
- `requirements.txt`: Python package list for the optimized webhook-only service.
- `app.py`: Flask app exposing `GET/POST /x/webhook` and `GET /healthz`. It verifies X CRC/signatures, writes webhook payloads to `state/events_inbox.jsonl`, and disables in-process background work on PythonAnywhere.
- `pythonanywhere_wsgi.py`: PythonAnywhere WSGI entrypoint. This imports the Flask app as `application`.
- `pythonanywhere_worker.py`: Always-on task entrypoint for PythonAnywhere. It scans `state/events_inbox.jsonl`, processes unhandled mentions, calls OpenAI, posts X replies, and records success/failure state.
- `admin.py`: Operational CLI for X setup and recovery: resolve bot user, create/validate webhook, subscribe/check/list subscriptions, replay X events, and retry failed jobs.
- `settings.py`: Central configuration loader and validation. Reads `OPTIMIZED-PYTHONANYWHERE/.env`, validates `PUBLIC_BASE_URL`, and defines paths for data/state.
- `service.py`: Core runtime pipeline. Filters webhook events, dedupes tweet IDs, builds context, calls the responder, posts replies, and writes processed/failure records.
- `context_builder.py`: Local MMA context builder. Loads `data/fighter_info.csv` and `data/event_data_sherdog.csv`, matches fighter names, and creates compact fight context for OpenAI.
- `openai_service.py`: OpenAI Responses API wrapper. Builds the prompt, calls the configured model, extracts reply text, and enforces the X reply character limit.
- `x_api.py`: X API wrapper. Handles CRC HMAC generation, webhook signature verification, bearer-token admin calls, OAuth subscription paths, and OAuth1a reply posting.
- `storage.py`: JSON/JSONL file-backed persistence helpers for inbox, processed IDs, replies, failures, and webhook config.
- `tests/test_optimized.py`: Unit and integration tests with mocked OpenAI/X clients for CRC, signatures, dedupe, matching, truncation, webhook processing, retries, and worker checkpoints.
- `data/fighter_info.csv`: Local fighter profile dataset used by the context builder.
- `data/event_data_sherdog.csv`: Local fight history dataset used by the context builder.
- `state/.gitkeep`: Keeps the state directory in git. Runtime JSON/JSONL files in this directory are generated on the server.
- `systemd/fight-agent-optimized.service`: Example systemd service for a VPS/Raspberry Pi style deployment.
- `nginx/fight-agent-optimized.conf`: Example Nginx reverse proxy for a VPS/Raspberry Pi style deployment.

## PythonAnywhere Runtime Process

1. X app sends Account Activity webhook traffic to `https://bestisblessed.pythonanywhere.com/x/webhook`.
2. PythonAnywhere web app loads `pythonanywhere_wsgi.py`, which exposes the Flask `application` from `app.py`.
3. `GET /x/webhook?crc_token=...` returns the X CRC `response_token` signed with `X_API_SECRET`.
4. `POST /x/webhook` verifies `x-twitter-webhooks-signature`, parses the JSON payload, appends it to `state/events_inbox.jsonl`, and returns `200` quickly.
5. The PythonAnywhere Always-on task runs `pythonanywhere_worker.py` separately from the web request process.
6. The worker loads `OPTIMIZED-PYTHONANYWHERE/.env`, validates runtime settings, loads the local CSV datasets, and repeatedly scans `state/events_inbox.jsonl`.
7. For each unprocessed `tweet_create_events` mention, `service.py` skips duplicates, skips self-authored bot replies, and confirms the tweet actually mentions `BOT_USERNAME`.
8. `context_builder.py` matches up to two fighters from the tweet and builds compact local MMA context.
9. `openai_service.py` calls the OpenAI Responses API using `OPENAI_MODEL`, `OPENAI_MAX_OUTPUT_TOKENS`, and `OPENAI_TIMEOUT_SECONDS`, then trims the final reply to `REPLY_CHAR_LIMIT`.
10. `x_api.py` posts one direct X reply with `POST /2/tweets` using OAuth1a user credentials.
11. Successful replies are written to `state/replies.jsonl`, and their dedupe keys are written to `state/processed_event_ids.jsonl` with reason `replied`.
12. Failed jobs are written to `state/failed_jobs.jsonl` with phase and error details. Retryable failures can be reprocessed with `python admin.py retry-failed`.
13. Webhook and subscription setup is managed manually from the PythonAnywhere console with `admin.py`: `resolve-bot-user`, `create-webhook`, `validate-webhook`, `subscribe`, `check-subscription`, and `list-subscriptions`.
14. PythonAnywhere replaces the VPS-specific `systemd/` and `nginx/` assets. The web app handles HTTPS/WSGI, and the Always-on task handles background processing.
