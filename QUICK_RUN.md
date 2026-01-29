# Quick Run Guide - Generate Post Now

## Current Status

✅ All credentials configured in `.env`:
- OpenRouter API Key
- Notion API Key & Page ID  
- Mastodon Access Token
- Replicate API Token (for comic images)
- Telegram Bot Token & Chat ID

## To Generate Your Post

### Option 1: Using the Script (Recommended)

```bash
cd /Users/sasa/Truststacksocial/TrustStackSocial
./run_post_generation.sh
```

This script will:
1. Activate virtual environment
2. Install missing dependencies (if needed)
3. Generate the post

### Option 2: Manual Steps

```bash
cd /Users/sasa/Truststacksocial/TrustStackSocial
source venv/bin/activate
pip install -r requirements.txt
python main.py generate-pending-post
```

### Option 3: With Custom Options

```bash
source venv/bin/activate
python main.py generate-pending-post \
  --style professional \
  --temperature 0.7 \
  --max-articles 3
```

## What Happens Next

1. **Fetches News** - Gets latest AI/ML articles from RSS feeds
2. **Generates Post** - Creates social media post incorporating news
3. **Generates Comic Image** - Creates comic-style image via Replicate
4. **Adds Logo** - Includes TrustStack logo (if in `assets/logos/`)
5. **Sends to Telegram** - Sends preview with images for approval
6. **You Approve** - Click ✅ Approve in Telegram
7. **Posts to Mastodon** - Automatically posts after approval

## Check Telegram

After running, check Telegram chat (ID: 8431676322). You'll see:
- Post content
- Comic image
- Logo (if available)
- Article summaries
- ✅ Approve / ❌ Reject buttons

## Troubleshooting

### Network Issues
If you see network errors, check your internet connection and try again.

### Missing Dependencies
The script will auto-install, or manually run:
```bash
pip install -r requirements.txt
```

### No Logo Found
Place your logo at: `assets/logos/truststack_logo.png`

---

**Ready to go!** Run `./run_post_generation.sh` when you have network connectivity.
