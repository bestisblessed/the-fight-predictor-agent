# YouTube Outline: Twitter Agent (Current Production Stack)

## Packages and Tools Needed (Quick Overview)

### Core runtime and automation
- **Linux server + Cron**: Runs the bot every 10 minutes on a fixed schedule.
- **pyenv Python shim (`$HOME/.pyenv/shims/python`)**: Ensures the expected Python version is used in cron.
- **Healthchecks.io ping script**: Confirms each cron run finished and reports health.

### Python packages in active use
- **openai (`>=2.0.0`)**: Calls the Responses API (`gpt-5-mini`) and Code Interpreter.
- **python-dotenv**: Loads API credentials from `.env`.
- **python-docx**: Reads the downloaded `.docx` mention inbox.
- **requests**: Downloads generated images and supports HTTP operations.
- **tweepy**: Posts replies (and retweets) on X/Twitter.
- **google-auth + google-api-python-client**: Exports the mention `.docx` from Google Drive using a service account.
- **Pillow**: Included in project dependencies; image handling support for generated assets.

### External services and data
- **X/Twitter API**: Source and destination for mentions/replies.
- **Google Drive**: Upstream storage for the mention document (`TheFightAgentMentions.docx`).
- **OpenAI Responses API + Code Interpreter**: Generates analysis and optional charts/images.
- **MMA datasets (`fighter_info.csv`, `event_data_sherdog.csv`)**: Attached to Code Interpreter for data-backed answers.

---

## Step-by-Step Build and Runtime Walkthrough

## 1. Define the end-to-end architecture
Explain the system as a cron-driven polling pipeline:
1. Download latest mention inbox from Google Drive.
2. Parse tweets and detect unprocessed mention IDs.
3. Generate response with OpenAI + datasets.
4. Reply on X/Twitter.
5. Log status and emit healthcheck markers.

Why this matters for viewers:
- They need to see this is not a webhook architecture.
- The system is batch/polling based and intentionally simple to schedule.

## 2. Provision the server and schedule cron
Show the production cron style from `AGENTS.md` and `PRODUCTION/run_agent_cron.sh`.

What to explain:
- Why `set -euo pipefail` is used.
- Why output is appended to `PRODUCTION/cron.log`.
- Why cron interval is every 10 minutes.

Teaching point:
- In polling agents, reliability starts with predictable scheduling and logs.

## 3. Configure credentials and environment
Walk through required secrets:
- `OPENAI_API_KEY`
- `TWITTER_API_KEY`
- `TWITTER_API_SECRET`
- `TWITTER_ACCESS_TOKEN`
- `TWITTER_ACCESS_SECRET`
- Google service account JSON in `PRODUCTION/credentials/service-account.json`

Explain separation:
- `.env` for runtime API keys.
- JSON credential file for Google Drive service account auth.

## 4. Build mention ingestion from Google Drive
Use `PRODUCTION/download_mentions_from_drive_service_account.py`.

What happens:
- Authenticate service account with Drive read-only scope.
- Export a specific Google Drive file ID as `.docx`.
- Save to `data/TheFightAgentMentions.docx`.

Why this exists:
- Mentions are being bridged into Drive instead of read directly from Twitter API in production.

## 5. Parse mentions and dedupe by tweet ID
Use `PRODUCTION/assistant_from_tweets.py` parsing logic.

Show document format assumptions:
- Blocks with separators.
- `Tweet:` line for content.
- `Link:` line containing tweet URL and ID.

Explain state handling:
- Processed IDs live in `data/processed_tweet_ids.txt`.
- If ID already exists, skip.

## 6. Prepare OpenAI Code Interpreter datasets
Cover dataset flow:
- Read `data/fighter_info.csv` and `data/event_data_sherdog.csv`.
- Upload once if needed.
- Cache uploaded file IDs in `data/uploaded_file_ids.json`.
- Reuse valid file IDs on future runs.

Why it matters:
- Avoids re-upload cost and latency every cron cycle.

## 7. Generate replies with Responses API
Use `process_tweet_with_responses_api()` in production script.

Explain configuration:
- Model: `gpt-5-mini`
- Tools: Code Interpreter container with dataset `file_ids`
- Polling status until terminal state
- Output extraction from `output_text` and `output` blocks

What viewers should notice:
- Prompt includes strict analyst persona and “data-backed answers” behavior.
- Can return both text and image outputs.

## 8. Persist outputs locally
Current script writes:
- Text response to `responses/<tweet_id>.txt`
- Optional generated image to `files/<tweet_id>.png`

Explain why:
- Local traceability and debugging for each mention.
- Backup if posting step fails.

## 9. Post reply on X/Twitter
Use `PRODUCTION/reply_single_tweet.py`.

Current behavior to explain:
- Replies to original mention ID.
- Uploads media if matching image file exists.
- Attempts a retweet of the reply.

Call out this as a quality-review moment:
- Current logs show cases where posting failed (402) but upstream script still logged success.

## 10. Logging and operational visibility
Use `cron.log` as the run ledger.

What to show in video:
- Start and completion markers with timestamps.
- `HEALTHCHECK_OK` sentinel line.
- Typical no-op cycles (“Found new tweets: 0”).
- Rare cycles where new tweets are processed.

## 11. Failure modes seen in real logs
Use real examples from your `cron.log`:
- Google Drive export `HttpError 500`
- TLS/read timeouts to Drive
- `PackageNotFoundError` when expected docx isn’t present
- Twitter post failures (`402 Payment Required`) that can be mis-labeled as success

Why include this:
- Real reliability lessons are more useful than a perfect demo.

## 12. Legacy variants and why they were used
Briefly explain `PRODUCTION-WITH-IFTTT` and `PRODUCTION-WITH-IFTTT-DOCS`:
- Historical integrations with Sheets/Docs for handoff and automation workflows.
- Not the active production runtime now.

## 13. Generalize for any Twitter agent niche
Close the video by showing what is reusable:
- Scheduler pattern
- Deduping and persistence
- LLM generation step
- Reply pipeline

And what is domain-specific:
- MMA datasets
- prompt style
- fighter-analysis instructions

---

## Suggested On-Screen Deliverables
- Architecture diagram (polling flow).
- `.env` template and credentials checklist.
- `cron` line and `run_agent_cron.sh` walkthrough.
- Before/after run snapshots from `cron.log`.
- One successful processed tweet trace from detection to posted reply.
