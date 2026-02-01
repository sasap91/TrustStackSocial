# Colab Notebook Integration

This directory contains scripts and examples for running the TrustStackSocial HITL workflow in Google Colab, plus the RAG workshop reference notebook.

## RAG Workshop Notebook

**`SASA_workshop_4_RAG.ipynb`** – Reference implementation for RAG with hybrid search:

- **Part 1**: SQLite + FTS5 + sqlite-vec (embeddings_meta, vec_embeddings, embeddings_fts)
- **Part 2**: Document chunking by `##` headers; local embeddings with fastembed (MiniLM-L6-v2, 384 dim)
- **Part 3**: BM25 (FTS5) + semantic (sqlite-vec) hybrid search; score fusion
- **Part 4**: Post generation with RAG context (retrieve_context → format_context_for_prompt → LLM)

The project’s RAG integration (Notion docs → chunk → SQLite → hybrid retrieval in `create_posts`) follows this notebook’s patterns: same chunking style, sqlite-vec + FTS5, fastembed, and hybrid search, with docs sourced from the Notion API instead of local `.md` files.

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
