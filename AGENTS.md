# AGENTS.md - Coding Guidelines for AI Agents

## Project Overview

A Python-based AI agent that monitors Twitter/X mentions, sends them to OpenAI's Responses API with Code Interpreter and MMA datasets attached, and replies with predictions/analysis.

Three environments:
- **DEV/**: Development and testing scripts
- **PRODUCTION/**: Active production bot (what runs on the server)
- **PRODUCTION-WITH-IFTTT/**: Older variant with IFTTT integration
- **PRODUCTION-WITH-IFTTT-DOCS/**: Older variant with Google Docs integration

## Deployment (Server / Cron Job)

The bot runs on a remote server as a cron job every 10 minutes:

```
*/10 * * * * /home/trinity/the-fight-predictor-agent/PRODUCTION/run_agent_cron.sh >> /home/trinity/the-fight-predictor-agent/PRODUCTION/cron.log 2>&1; status=$?; /home/trinity/healthcheckio_push.sh /home/trinity/the-fight-predictor-agent/PRODUCTION/cron.log https://hc-ping.com/c22bfc9e-42ad-4669-991b-90f8fe14f7fa "$status" "HEALTHCHECK_OK: fight-predictor-agent"
```

`run_agent_cron.sh` does the following each run:
1. Logs start time to `cron.log`
2. Runs `download_mentions_from_drive_service_account.py` — downloads new mentions from Google Drive
3. Runs `assistant_from_tweets.py` — processes mentions and posts replies via Twitter
4. Logs completion and a healthcheck sentinel string to `cron.log`

Python is invoked via pyenv: `$HOME/.pyenv/shims/python`

Healthcheck pings [healthchecks.io](https://healthchecks.io) after each run to confirm the job completed.

## Running Scripts Locally

```bash
# Development
python DEV/post_tweet.py
python DEV/check_mentions.py
python DEV/reply_single_tweet.py <tweet_id> <reply_text>

# Production (run from PRODUCTION/ directory)
python PRODUCTION/download_mentions_from_drive_service_account.py
python PRODUCTION/assistant_from_tweets.py
python PRODUCTION/post_tweet_with_rate_check.py

# Tale of the Tape generators
python tott_generator.py          # Word document
python tott_generator_pdf.py      # PDF
python tott_generator_png.py      # PNG image
```

### Testing Approach
- No formal test framework — test manually in DEV/ first
- Check `data/` and `responses/` output files for verification
- Monitor rate limits when interacting with Twitter API

## Code Style Guidelines

### Imports
- Standard library first, third-party second, local last
- Use `from dotenv import load_dotenv` for environment variables

```python
import os
import time
import json
import sys
from datetime import datetime, timezone

import requests
import openai
from dotenv import load_dotenv
from PIL import Image
```

### Environment Variables
- Always call `load_dotenv()` at the top
- Never hardcode credentials
- Fail fast if required credentials are missing

```python
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    print("Error: Missing API key.")
    exit()
```

### Naming Conventions
- **Files**: `snake_case.py`
- **Variables/Functions**: `snake_case`
- **Constants**: `UPPER_CASE`

### Function Structure
- Use `def main():` as entry point
- Wrap with `if __name__ == "__main__": main()`

### Error Handling
- Use try/except for all API calls
- Handle specific exceptions before general `Exception`
- Print descriptive error messages with context
- Use `exit()` or `sys.exit()` for fatal errors

### File and Directory Management
- `os.makedirs('data', exist_ok=True)` for directory creation
- Store credentials in `credentials/` (not in git)
- Store data files in `data/`
- Store generated responses in `responses/`

### API Integration

**OpenAI Responses API** (primary):
```python
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
response = client.responses.create(
    model="gpt-5-mini",
    instructions=SYSTEM_INSTRUCTIONS,
    input=[{"role": "user", "content": tweet_text}],
    tools=tools if tools else [],
    max_output_tokens=MAX_OUTPUT_TOKENS,
    store=True
)
```

**Twitter (HTTP + OAuth via subprocess or requests)**:
- Uses direct API calls, not tweepy
- OAuth credentials loaded from environment variables

**Google Drive (service account)**:
```python
from google.oauth2 import service_account
from googleapiclient.discovery import build
```

### Output and Logging
- Use `print()` for logging (no formal logging framework)
- Print status at key steps with IDs and timestamps
- Append to `cron.log` on the server

### Security
- Never commit API keys or credentials
- Secrets in `.env` files (in `.gitignore`)
- JSON credential files in `credentials/` directory

## Project Structure

```
/Users/td/Code/the-fight-predictor-agent/
├── AGENTS.md
├── assistant.py                      # Interactive OpenAI chatbot
├── assistant_template.py
├── tott_generator.py                 # Tale of the Tape (Word)
├── tott_generator_pdf.py             # Tale of the Tape (PDF)
├── tott_generator_png.py             # Tale of the Tape (PNG)
├── test_responses_api.py
├── instructions.md                   # Assistant system prompts
├── notes.md
├── requirements.txt
├── credentials/                      # API credentials (not in git)
├── data/
├── responses/
├── DEV/                              # Development scripts
│   ├── check_mentions.py
│   ├── post_tweet.py
│   ├── reply_single_tweet.py
│   ├── reply_tweets.py
│   ├── assistant_from_tweets.py
│   └── ...
└── PRODUCTION/                       # Active production bot
    ├── assistant_from_tweets.py      # Main agent loop
    ├── download_mentions_from_drive_service_account.py
    ├── download_mentions_from_drive.py
    ├── post_tweet_with_rate_check.py
    ├── reply_single_tweet.py
    ├── run_agent_cron.sh             # Cron entrypoint
    ├── run_agent.sh
    ├── credentials/
    ├── data/
    └── responses/
```

## Key Dependencies

See `requirements.txt` for pinned versions.

- `openai>=2.0.0` — Responses API (requires 2.x for Responses API support)
- `python-dotenv` — Environment variable management
- `requests` — HTTP library
- `python-docx` — Word document generation
- `Pillow` — Image processing
- `pandas` — Data manipulation (tott generators)
- `google-auth`, `google-auth-oauthlib`, `google-api-python-client` — Google Drive access
