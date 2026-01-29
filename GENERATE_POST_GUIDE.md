# Generate Social Media Post Guide

## Quick Start

To generate a post with news, logo, and comic image, follow these steps:

### 1. Activate Virtual Environment

```bash
cd /Users/sasa/Truststacksocial/TrustStackSocial
source venv/bin/activate
```

### 2. Install/Update Dependencies

```bash
pip install -r requirements.txt
```

### 3. Update .env File (if needed)

Your `.env` file currently has:
- ✅ OPENROUTER_API_KEY
- ✅ NOTION_API_KEY  
- ✅ NOTION_PAGE_ID
- ✅ MASTODON_ACCESS_TOKEN

**Optional but recommended for full functionality:**
- ⚠️ REPLICATE_API_TOKEN (for comic image generation)
- ⚠️ TELEGRAM_BOT_TOKEN (for approval workflow)
- ⚠️ TELEGRAM_CHAT_ID (for approval workflow)

Add these to your `.env` file if you have them:

```bash
# Replicate API Configuration (optional - for comic image generation)
REPLICATE_API_TOKEN=your_replicate_api_token_here

# Telegram Bot Configuration (optional - for approval workflow)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here
```

### 4. Add TrustStack Logo (Optional)

Place your TrustStack logo in `assets/logos/` directory:
- Supported formats: PNG, JPG, JPEG, GIF, WEBP
- Recommended name: `truststack_logo.png`

### 5. Generate Post

**Option A: With Telegram Approval (Recommended)**
```bash
python main.py generate-pending-post
```

This will:
1. Fetch latest news articles related to TrustStack
2. Generate a post incorporating the news
3. Generate a comic image based on the news (if REPLICATE_API_TOKEN is set)
4. Add TrustStack logo (if available)
5. Send to Telegram for approval
6. After approval, post to Mastodon

**Option B: Direct Post (No Approval)**
```bash
# First generate the post
python main.py generate-posts --count 1

# Then post it
python main.py post-to-mastodon --index 0
```

### 6. Approve Post via Telegram

If you used Option A:
1. Check your Telegram chat
2. You'll see a message with the post preview, images, and Approve/Reject buttons
3. Click "✅ Approve" to post to Mastodon
4. Click "❌ Reject" to archive the post (you can provide feedback)

## What Gets Generated

- **Post Content**: AI-generated social media post incorporating latest news
- **Comic Image**: Visual representation of the news (if REPLICATE_API_TOKEN is set)
- **Logo**: TrustStack logo (if available in assets/logos/)
- **News Context**: Latest articles from RSS feeds
- **Quotes**: Key quotes extracted from articles

## Troubleshooting

### "Module not found" errors
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### "REPLICATE_API_TOKEN not set"
- Comic image generation will be skipped
- Post will still be generated with logo (if available)
- Add REPLICATE_API_TOKEN to .env to enable comic images

### "Telegram credentials not set"
- Post will be created but not sent for approval
- You can manually approve: `python main.py approve-post <id>`
- Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env

### "No logo found"
- Place your logo in `assets/logos/truststack_logo.png`
- Or update `config.yaml` to point to your logo file

## Example Output

```
✓ Generated and queued post for approval!
  Pending Post ID: 1
  Style: professional
  Articles used: 3
  Quotes included: 2
  Has logo: True
  Has comic image: True

Check Telegram for approval request.
```
