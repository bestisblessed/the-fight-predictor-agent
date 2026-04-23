# AGENTS.md - Coding Guidelines for AI Agents

## Project Overview

This is a Python-based Twitter bot for MMA fight prediction and automation. The project has three environments:
- **DEV/**: Development scripts and testing
- **PRODUCTION/**: Production-ready Twitter bot scripts
- **PRODUCTION-WITH-IFTTT/**: Production with IFTTT integration
- **PRODUCTION-WITH-IFTTT-DOCS/**: Production with Google Docs integration

## Build/Lint/Test Commands

### No Formal Test Suite
This project does not have a formal test framework configured. Testing is done by:
1. Running scripts manually in DEV/ environment first
2. Checking output for errors
3. Verifying Twitter API interactions in the DEV environment

### Running Individual Scripts
```bash
# Development environment
python DEV/post_tweet.py
python DEV/check_mentions.py
python DEV/reply_single_tweet.py <tweet_id> <reply_text>

# Production environment
python PRODUCTION/assistant_from_tweets.py
python PRODUCTION/post_tweet_with_rate_check.py

# Tale of the Tape generators
python tott_generator.py          # Generate Word document
python tott_generator_pdf.py      # Generate PDF
python tott_generator_png.py      # Generate PNG image
```

### Manual Testing Approach
- Test API credentials first with simple scripts
- Use DEV/ environment for all new features
- Check mentions.json and response files for verification
- Monitor rate limits when interacting with Twitter API

## Code Style Guidelines

### Imports
- **Standard library imports first** (e.g., `import os`, `import time`, `import json`)
- **Third-party imports second** (e.g., `import tweepy`, `import openai`, `import pandas`, `import requests`)
- **Local imports last** (none in this codebase currently)
- Use `from dotenv import load_dotenv` for environment variable management

Example:
```python
import os
import time
import json
import sys
from datetime import datetime, timezone

import requests
import tweepy
import openai
from dotenv import load_dotenv
from PIL import Image
```

### Environment Variables
- Always use `load_dotenv()` at the start of scripts
- Load credentials from environment variables, never hardcode
- Check for required credentials before proceeding
- Use `.env` files for local development

Pattern:
```python
load_dotenv()
API_KEY = os.getenv("TWITTER_API_KEY")
if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
    print("Error: Missing one or more Twitter API credentials.")
    exit()
```

### Naming Conventions
- **Files**: Use `snake_case.py` (e.g., `check_mentions.py`, `reply_single_tweet.py`)
- **Variables**: Use `snake_case` (e.g., `tweet_id`, `response_data`)
- **Constants**: Use `UPPER_CASE` for module-level constants (e.g., `API_KEY`, `SCOPES`)
- **Functions**: Use `snake_case` (e.g., `post_tweet_v2()`, `get_user_id()`)

### Function Structure
- Use `def main():` as entry point
- Wrap execution in `if __name__ == "__main__": main()`
- Accept command-line arguments with `sys.argv` when needed

Example:
```python
def post_tweet_v2(text):
    try:
        response = client.create_tweet(text=text)
        print(f"Tweet posted! ID: {response.data['id']}")
    except tweepy.errors.Forbidden as e:
        print("Error: Forbidden - Check your app's access level or API tier.")
    except Exception as e:
        print(f"Unexpected error: {e}")

def main():
    tweet_text = input("Enter your tweet: ")
    post_tweet_v2(tweet_text)

if __name__ == "__main__":
    main()
```

### Error Handling
- Use try/except blocks for API calls
- Handle specific exceptions first (e.g., `tweepy.errors.Forbidden`)
- Catch general `Exception` as fallback
- Print descriptive error messages
- Use `exit()` or `sys.exit()` for fatal errors

### File and Directory Management
- Create directories with `os.makedirs('data', exist_ok=True)`
- Use relative paths from script location
- Store credentials in `credentials/` directory
- Store data files in `data/` directory
- Store generated reports in `reports/` directory

### API Integration Patterns

**Twitter API (Tweepy)**:
```python
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)
```

**OpenAI API**:
```python
client = openai.OpenAI(api_key=openai.api_key)
thread = client.beta.threads.create()
```

**HTTP Requests with OAuth**:
```python
from requests_oauthlib import OAuth1
oauth = OAuth1(api_key, api_secret, access_token, access_secret)
response = requests.post(url, auth=oauth, headers=headers, data=payload)
```

### Data Persistence
- Use JSON for structured data: `json.dump(data, f, indent=4)`
- Track processed IDs in text files (e.g., `data/processed_tweet_ids.txt`)
- Save responses with tweet IDs as filenames
- Use `.docx` files for mentions data from Google Drive

### Output and Logging
- Use `print()` statements for logging (no formal logging framework)
- Print status updates at key steps
- Include IDs and timestamps in output messages
- Format rate limit information for readability

### Commenting
- Use comments for code sections (e.g., `# CHECKING EVERY 15 MINUTES`)
- Comment out old code at the bottom of files instead of deleting
- Use inline comments sparingly, focus on readable code

### Security
- Never commit API keys or credentials
- Store secrets in `.env` files (already in `.gitignore`)
- Use `.json` credential files in `credentials/` directory
- Never print sensitive tokens in output

## Project Structure

```
/Users/td/Code/the-fight-predictor-agent/
├── assistant.py                      # Interactive OpenAI chatbot
├── tott_generator*.py               # Tale of the Tape generators
├── instructions.md                  # Assistant prompts
├── notes.md                         # Project documentation
├── DEV/                             # Development scripts
│   ├── data/                        # Test data files
│   ├── check_mentions.py
│   ├── post_tweet.py
│   └── ...
├── PRODUCTION/                      # Production scripts
│   ├── assistant_from_tweets.py
│   ├── post_tweet_with_rate_check.py
│   └── ...
├── PRODUCTION-WITH-IFTTT/           # IFTTT integration
├── PRODUCTION-WITH-IFTTT-DOCS/      # Google Docs integration
├── credentials/                     # API credentials (not in git)
├── data/                           # Data storage
└── reports/                        # Generated reports
```

## Key Dependencies

- `tweepy` - Twitter API client
- `openai` - OpenAI API client
- `requests` - HTTP library
- `requests_oauthlib` - OAuth authentication
- `python-dotenv` - Environment variable management
- `pandas` - Data manipulation
- `python-docx` - Word document generation
- `google-auth`, `google-auth-oauthlib`, `google-api-python-client` - Google APIs
- `Pillow` - Image processing
