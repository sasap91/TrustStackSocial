# Quick Start Guide

Get up and running with TrustStack Social Media Automation in 5 minutes!

## 1. Setup (One-time)

Run the setup script:

```bash
bash setup.sh
```

Or manually:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure API Keys

Create a `.env` file with your credentials:

```bash
OPENROUTER_API_KEY=sk-or-v1-xxxxx
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

NOTION_API_KEY=secret_xxxxx
NOTION_PAGE_ID=xxxxx

MASTODON_ACCESS_TOKEN=xxxxx
MASTODON_API_BASE_URL=https://mastodon.social
```

### Where to get API keys:

- **Openrouter**: https://openrouter.ai/keys
- **Notion**: https://www.notion.so/my-integrations
- **Mastodon**: Your instance → Settings → Development → New Application

## 3. Run Your First Workflow

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# Generate 3 posts and fetch 5 articles (preview mode)
python main.py full-workflow

# Review generated content
cat output/posts.json
cat output/articles.json
cat output/comments.json
```

## 4. Post to Mastodon

```bash
# Post your first generated post
python main.py post-to-mastodon --index 0

# Or post a comment about an article
python main.py post-comments --index 0
```

## Common Commands

### Generate Content

```bash
# Generate 5 social media posts
python main.py generate-posts --count 5

# Fetch 10 top AI/ML articles
python main.py fetch-articles --count 10

# Generate comments for articles
python main.py generate-comments
```

### Post Content

```bash
# Interactive post selection
python main.py post-to-mastodon

# Post specific post
python main.py post-to-mastodon --index 0

# Preview before posting
python main.py post-to-mastodon --index 0 --preview
```

### Full Automation

```bash
# Preview workflow (no posting)
python main.py full-workflow

# Full workflow with Mastodon posting
python main.py full-workflow --post-to-mastodon
```

## Troubleshooting

### Command not found: python

Use `python3` instead:

```bash
python3 main.py full-workflow
```

### Configuration errors

Make sure your `.env` file exists and has all required keys set.

### Notion API errors

1. Verify your integration has access to the page
2. Check the page ID is correct
3. Ensure the API key is valid

### Can't install dependencies

Make sure you're in the virtual environment:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

## Daily Workflow Example

```bash
# Morning routine
source venv/bin/activate

# Generate fresh content
python main.py generate-posts --count 5

# Pick and post your favorite
python main.py post-to-mastodon

# Check for new articles and engage
python main.py fetch-articles --count 10
python main.py generate-comments
python main.py post-comments --index 0
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Customize RSS feeds in `config.yaml`
- Adjust keywords for article filtering
- Experiment with different post styles

---

Need help? Check [README.md](README.md) for detailed troubleshooting.

