# TrustStack Social Media Automation

A Python-based social media automation system that generates AI-powered content for TrustStack, posts to Mastodon, and creates thoughtful comments on industry articles.

## Features

- **AI-Powered Content Generation**: Uses Openrouter (with Claude, GPT, or other LLMs) to generate engaging social media posts
- **Notion Integration**: Fetches company information from Notion to inform content generation
- **Mastodon Integration**: Posts content directly to Mastodon with full API support
- **Article Monitoring**: Fetches top AI/ML articles from major tech blogs via RSS
- **Smart Commenting**: Generates thoughtful, contextual comments on industry articles
- **Manual Control**: Run workflows on-demand with CLI commands
- **Review Workflow**: Preview and review all generated content before posting

## Architecture

```
┌─────────────┐
│   Notion    │──────┐
│   API       │      │
└─────────────┘      │
                     ▼
              ┌──────────────┐        ┌──────────────┐
              │    Post      │───────▶│  Mastodon    │
              │  Generator   │        │    API       │
              └──────────────┘        └──────────────┘
                     ▲
                     │
              ┌──────────────┐
              │  Openrouter  │
              │     LLM      │
              └──────────────┘
                     ▲
                     │
┌─────────────┐      │         ┌──────────────┐
│  RSS Feeds  │──────┼────────▶│   Comment    │
│ (Tech Blogs)│      │         │  Generator   │
└─────────────┘      └─────────└──────────────┘
```

## Prerequisites

- Python 3.8 or higher
- API credentials for:
  - Openrouter (https://openrouter.ai/)
  - Notion (https://www.notion.so/my-integrations)
  - Mastodon (your instance's developer settings)

## Installation

1. **Clone the repository** (or navigate to the project directory):
   ```bash
   cd TrustStackSocial
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Create a `.env` file in the project root with your API credentials:
   ```bash
   # Openrouter API Configuration
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
   
   # Notion API Configuration
   NOTION_API_KEY=your_notion_api_key_here
   NOTION_PAGE_ID=your_notion_page_id_here
   
   # Mastodon API Configuration
   MASTODON_ACCESS_TOKEN=your_mastodon_access_token_here
   MASTODON_API_BASE_URL=https://mastodon.social
   ```

## Getting API Credentials

### Openrouter API Key
1. Go to https://openrouter.ai/
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key to your `.env` file

### Notion API Key and Page ID
1. Go to https://www.notion.so/my-integrations
2. Click "New integration"
3. Give it a name (e.g., "TrustStack Social")
4. Copy the "Internal Integration Token" to your `.env` file as `NOTION_API_KEY`
5. Share your company information page with the integration
6. Copy the page ID from the URL (e.g., `https://notion.so/Your-Page-abc123` → `abc123`)

### Mastodon Access Token
1. Log in to your Mastodon instance
2. Go to Settings → Development → New Application
3. Give it a name and set appropriate scopes (read, write)
4. Click Submit
5. Copy the "Your access token" to your `.env` file

## Usage

The system provides a CLI with several commands:

### Generate Social Media Posts

Generate posts based on your Notion content:

```bash
python main.py generate-posts --count 5
```

Options:
- `--count, -c`: Number of posts to generate (default: 5)
- `--output, -o`: Output file path (default: output/posts.json)
- `--temperature, -t`: Sampling temperature for variety (default: 0.7)

### Post to Mastodon

Post generated content to Mastodon:

```bash
# Interactive selection
python main.py post-to-mastodon

# Post specific post by index
python main.py post-to-mastodon --index 0

# Preview without posting
python main.py post-to-mastodon --index 0 --preview
```

Options:
- `--file, -f`: Input file with posts (default: output/posts.json)
- `--index, -i`: Post index to post (0-based)
- `--all`: Post all posts from file
- `--preview`: Preview without actually posting

### Fetch Top Articles

Fetch trending AI/ML articles from tech blogs:

```bash
python main.py fetch-articles --count 10
```

Options:
- `--count, -c`: Number of top articles to fetch (default: 10)
- `--output, -o`: Output file path (default: output/articles.json)
- `--min-age-hours`: Minimum article age in hours (default: 1)
- `--max-age-days`: Maximum article age in days (default: 7)

### Generate Comments

Generate thoughtful comments on articles:

```bash
python main.py generate-comments
```

Options:
- `--file, -f`: Input file with articles (default: output/articles.json)
- `--output, -o`: Output file path (default: output/comments.json)
- `--temperature, -t`: Sampling temperature (default: 0.7)

### Post Comments

Post generated comments to Mastodon:

```bash
# Interactive selection
python main.py post-comments

# Preview specific comment
python main.py post-comments --index 0 --preview
```

### Full Workflow

Run the complete automation workflow:

```bash
# Preview mode (doesn't post to Mastodon)
python main.py full-workflow

# With Mastodon posting enabled
python main.py full-workflow --post-to-mastodon
```

Options:
- `--post-count`: Number of posts to generate (default: 3)
- `--article-count`: Number of articles to fetch (default: 5)
- `--post-to-mastodon`: Actually post to Mastodon (default: preview only)

### Check Account Info

Display your Mastodon account information:

```bash
python main.py account-info
```

## Configuration

Edit `config.yaml` to customize:

- **RSS Feeds**: Add or remove tech blog RSS feeds
- **Keywords**: Customize keywords for article filtering
- **Article Settings**: Adjust fetching and filtering parameters
- **Post Settings**: Configure post generation parameters
- **Comment Settings**: Configure comment generation parameters

## File Structure

```
TrustStackSocial/
├── .env                    # API credentials (not in git)
├── .gitignore             # Git ignore rules
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── config.yaml           # Application configuration
├── main.py               # Main CLI application
├── src/
│   ├── __init__.py
│   ├── config.py         # Configuration management
│   ├── notion_client.py  # Notion API client
│   ├── openrouter_client.py  # Openrouter API client
│   ├── post_generator.py     # Post generation
│   ├── mastodon_client.py    # Mastodon API client
│   ├── article_fetcher.py    # RSS feed fetcher
│   ├── comment_generator.py  # Comment generation
│   └── utils.py          # Utility functions
└── output/               # Generated content (not in git)
    ├── posts.json
    ├── articles.json
    └── comments.json
```

## Workflow Examples

### Daily Social Media Routine

```bash
# 1. Generate 5 fresh posts
python main.py generate-posts --count 5

# 2. Review posts
cat output/posts.json

# 3. Post your favorite one (e.g., post #2)
python main.py post-to-mastodon --index 1

# 4. Fetch latest AI/ML articles
python main.py fetch-articles --count 10

# 5. Generate comments
python main.py generate-comments

# 6. Review and post a comment
python main.py post-comments
```

### Quick Automated Run

```bash
# Generate content and post automatically
python main.py full-workflow --post-to-mastodon --post-count 3 --article-count 5
```

## Customization

### Adding RSS Feeds

Edit `config.yaml` and add feeds to the `rss_feeds` section:

```yaml
rss_feeds:
  - name: "Your Blog Name"
    url: "https://yourblog.com/feed"
```

### Customizing Keywords

Edit the `article_keywords` section in `config.yaml`:

```yaml
article_keywords:
  - your custom keyword
  - another keyword
```

### Adjusting Post Style

The system generates posts in different styles:
- professional
- casual
- technical
- inspirational
- educational

Modify the `styles` parameter in `src/post_generator.py` to customize.

## Troubleshooting

### "Configuration errors found"

Make sure your `.env` file exists and contains all required variables:
```bash
OPENROUTER_API_KEY=...
NOTION_API_KEY=...
NOTION_PAGE_ID=...
MASTODON_ACCESS_TOKEN=...
```

### "Notion API error"

1. Verify your Notion API key is correct
2. Ensure the page is shared with your integration
3. Check that the page ID is correct

### "Mastodon authentication failed"

1. Verify your access token is correct
2. Check that your Mastodon instance URL is correct
3. Ensure the token has write permissions

### "Error fetching feed"

1. Check your internet connection
2. Verify the RSS feed URL is accessible
3. Some feeds may be rate-limited

## License

MIT License - Feel free to use and modify for your needs.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the configuration files
3. Check API credential validity
4. Examine logs in the terminal output

## Roadmap

Future enhancements:
- [ ] Scheduled automation with cron/scheduler
- [ ] Support for multiple social media platforms (Twitter/X, LinkedIn)
- [ ] Analytics and engagement tracking
- [ ] A/B testing for post variations
- [ ] Web dashboard for content management
- [ ] Image generation for posts
- [ ] Sentiment analysis for articles

---

Made with ❤️ for TrustStack

