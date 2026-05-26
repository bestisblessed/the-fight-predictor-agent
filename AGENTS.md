# AGENTS.md - Coding Guidelines for AI Agents

## Current Deployed Runtime Notice

Current deployed working folder is **OPTIMIZED-PYTHONANYWHERE/**. The active runtime is the PythonAnywhere web app plus the always-on worker. **PRODUCTION/** is a legacy cron deployment and should not be used for active bot changes unless explicitly requested.

## Project Overview

A Python-based AI agent that monitors Twitter/X mentions, sends them to OpenAI's Responses API with Code Interpreter and MMA datasets attached, and replies with predictions/analysis.

Current deployment:
- **OPTIMIZED-PYTHONANYWHERE/**: Active deployed bot for PythonAnywhere. Key runtime files include `pythonanywhere_wsgi.py` for the web app entrypoint, `pythonanywhere_worker.py` for the always-on worker, and `service.py` for shared bot behavior.
- Active local context uses `data/fighter_info.csv`, `data/event_data_sherdog.csv`, and matched fighters' career CSVs. Career CSV lookup prefers `OPTIMIZED-PYTHONANYWHERE/data/fighters/*.csv` and falls back to exact members in `OPTIMIZED-PYTHONANYWHERE/data/fighters.zip` without extracting the ZIP at runtime.

Other environments:
- **DEV/**: Development and testing scripts
- **PRODUCTION/**: Legacy cron deployment; inactive for current production behavior unless explicitly requested
- **PRODUCTION-WITH-IFTTT/**: Older variant with IFTTT integration
- **PRODUCTION-WITH-IFTTT-DOCS/**: Older variant with Google Docs integration

## Deployment (PythonAnywhere Web App + Always-On Worker)

The current deployed production bot runs from **OPTIMIZED-PYTHONANYWHERE/** on PythonAnywhere.

Primary active runtime files:
- `OPTIMIZED-PYTHONANYWHERE/pythonanywhere_wsgi.py`: PythonAnywhere WSGI entrypoint for the web app
- `OPTIMIZED-PYTHONANYWHERE/pythonanywhere_worker.py`: Always-on worker process
- `OPTIMIZED-PYTHONANYWHERE/service.py`: Shared service layer used by the active bot
- `OPTIMIZED-PYTHONANYWHERE/context_builder.py`: Local context builder; adds full career rows for matched fighter IDs when `data/fighters/*.csv` or `data/fighters.zip` contains the exact ID-suffixed file
- `OPTIMIZED-PYTHONANYWHERE/data/fighters.zip`: Deployment-friendly career CSV archive and OpenAI Code Interpreter fallback file

Do not make active bot changes in **PRODUCTION/** unless the user explicitly asks for the legacy cron implementation. The old **PRODUCTION/** cron job path is retained for reference only and is not the current deployed working folder.

Runtime data validation requires `fighter_info.csv`, `event_data_sherdog.csv`, and either `data/fighters/` with CSVs or `data/fighters.zip`. If both career sources exist, direct files win and the ZIP is used only as a fallback.

## Running Scripts Locally

```bash
# Development
python DEV/post_tweet.py
python DEV/check_mentions.py
python DEV/reply_single_tweet.py <tweet_id> <reply_text>

# Active production behavior (run from OPTIMIZED-PYTHONANYWHERE/ directory)
python OPTIMIZED-PYTHONANYWHERE/pythonanywhere_worker.py

# Legacy cron scripts (PRODUCTION/; use only if explicitly requested)
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
├── OPTIMIZED-PYTHONANYWHERE/         # Current deployed PythonAnywhere bot
│   ├── pythonanywhere_wsgi.py        # PythonAnywhere web app entrypoint
│   ├── pythonanywhere_worker.py      # Always-on worker
│   ├── service.py                    # Shared active bot behavior
│   ├── app.py
│   ├── settings.py
│   ├── data/fighters.zip             # Career CSV archive read directly, never extracted at runtime
│   ├── data/fighters/                # Optional direct career CSV folder, preferred when present
│   └── ...
└── PRODUCTION/                       # Legacy cron bot; inactive for current deployment
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
