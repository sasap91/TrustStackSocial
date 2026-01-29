# Colab Notebook Integration

This directory contains scripts and examples for running the TrustStackSocial HITL workflow in Google Colab.

## Quick Start in Colab

### 1. Install Dependencies

```python
!pip install python-telegram-bot python-dotenv sqlalchemy notion-client Mastodon.py openai feedparser requests pyyaml click beautifulsoup4 Pillow
```

### 2. Set Environment Variables

```python
import os

os.environ["TELEGRAM_BOT_TOKEN"] = "your_bot_token"
os.environ["TELEGRAM_CHAT_ID"] = "your_chat_id"
os.environ["OPENROUTER_API_KEY"] = "your_openrouter_key"
os.environ["OPENROUTER_MODEL"] = "anthropic/claude-3.5-sonnet"
os.environ["NOTION_API_KEY"] = "your_notion_key"
os.environ["NOTION_PAGE_ID"] = "your_notion_page_id"
os.environ["MASTODON_ACCESS_TOKEN"] = "your_mastodon_token"
os.environ["MASTODON_API_BASE_URL"] = "https://mastodon.social"
```

### 3. Upload Project Files

Upload the entire `TrustStackSocial` directory to Colab, or clone from repository:

```python
!git clone <your-repo-url>
%cd TrustStackSocial
```

### 4. Use the Colab-Compatible Script

```python
from notebooks.colab_hitl_workflow import generate_and_approve_post

# Generate and get approval
result = await generate_and_approve_post(
    style="professional",
    temperature=0.7,
    max_articles=3
)

print(result)
```

## Features

- **Async/await patterns** compatible with Colab's async environment
- **Feedback collection** - captures rejection reasons
- **Complete workflow** - generates post, sends for approval, handles response
- **Error handling** - handles timeouts and conflicts

## Example Notebook Cells

### Simple Message Test

```python
from notebooks.colab_hitl_workflow import send_simple_message

await send_simple_message(
    "Hello from Colab!",
    os.environ["TELEGRAM_BOT_TOKEN"],
    os.environ["TELEGRAM_CHAT_ID"]
)
```

### Approval Workflow

```python
from notebooks.colab_hitl_workflow import wait_for_approval_with_feedback

decision, reason = await wait_for_approval_with_feedback(
    "Sample post content here",
    os.environ["TELEGRAM_BOT_TOKEN"],
    os.environ["TELEGRAM_CHAT_ID"]
)

print(f"Decision: {decision}")
print(f"Reason: {reason}")
```

## Notes

- The script uses async patterns which work well in Colab
- Make sure only one bot instance is running at a time
- Feedback collection requires the bot server to be running
- For production, use the standalone `telegram_bot_server.py` instead
