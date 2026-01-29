# Ready to Generate Post! 🚀

## ✅ Configuration Complete

All credentials have been added to your `.env` file:

- ✅ **OpenRouter API Key** - Configured
- ✅ **Notion API Key & Page ID** - Configured  
- ✅ **Mastodon Access Token** - Configured
- ✅ **Replicate API Token** - Configured (for comic image generation)
- ✅ **Telegram Bot Token** - Configured
- ✅ **Telegram Chat ID** - Configured

## 🎯 Next Steps

### 1. Install Dependencies (when network is available)

```bash
cd /Users/sasa/Truststacksocial/TrustStackSocial
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Add TrustStack Logo (Optional but Recommended)

Place your TrustStack logo in:
```
assets/logos/truststack_logo.png
```

Supported formats: PNG, JPG, JPEG, GIF, WEBP

### 3. Generate Your Post!

Once dependencies are installed, run:

```bash
python main.py generate-pending-post
```

Or with custom options:

```bash
python main.py generate-pending-post --style professional --max-articles 3
```

## 📋 What Will Happen

1. **Fetch Latest News** - Gets latest AI/ML articles from RSS feeds
2. **Generate Post Content** - Creates a social media post incorporating the news
3. **Generate Comic Image** - Creates a comic-style image based on the news using Replicate
4. **Add Logo** - Includes TrustStack logo (if available)
5. **Send to Telegram** - Sends post preview with images for approval
6. **Approve/Reject** - You approve or reject via Telegram buttons
7. **Post to Mastodon** - After approval, automatically posts to Mastodon

## 🔍 Check Telegram

After running the command, check your Telegram chat (chat ID: 8431676322). You'll see:

- Post content preview
- Generated comic image
- TrustStack logo (if available)
- Article summaries
- Key quotes
- ✅ Approve button
- ❌ Reject button

Click **✅ Approve** to post to Mastodon!

## 🛠️ Troubleshooting

### If dependencies fail to install:
- Check your internet connection
- Try: `pip install --upgrade pip` first
- Install packages one by one if needed

### If image generation fails:
- Check that REPLICATE_API_TOKEN is correct
- The post will still be generated, just without comic image

### If Telegram doesn't work:
- Verify bot token and chat ID are correct
- Make sure you've started a conversation with your bot
- Check that the bot has permission to send messages

## 📝 Example Output

```
Generating post with news for approval...

✓ Generated and queued post for approval!
  Pending Post ID: 1
  Style: professional
  Articles used: 3
  Quotes included: 2
  Has logo: True
  Has comic image: True

Check Telegram for approval request.
```

## 🎨 Customization

You can customize the post generation:

```bash
# Different styles
python main.py generate-pending-post --style casual
python main.py generate-pending-post --style technical
python main.py generate-pending-post --style inspirational

# More articles
python main.py generate-pending-post --max-articles 5

# Different temperature (creativity)
python main.py generate-pending-post --temperature 0.9
```

---

**You're all set!** Once you have network connectivity and install dependencies, you can generate your first post! 🎉
