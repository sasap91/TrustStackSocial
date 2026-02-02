#!/usr/bin/env python3
"""
Quick script to generate a social media post with news, logo, and comic image
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

# Check required environment variables
required_vars = {
    'OPENROUTER_API_KEY': os.getenv('OPENROUTER_API_KEY'),
    'NOTION_API_KEY': os.getenv('NOTION_API_KEY'),
    'NOTION_PAGE_ID': os.getenv('NOTION_PAGE_ID'),
    'MASTODON_ACCESS_TOKEN': os.getenv('MASTODON_ACCESS_TOKEN'),
}

missing = [k for k, v in required_vars.items() if not v]
if missing:
    print(f"❌ Missing required environment variables: {', '.join(missing)}")
    print("Please set them in your .env file")
    sys.exit(1)

# Optional but recommended
optional_vars = {
    'REPLICATE_API_TOKEN': os.getenv('REPLICATE_API_TOKEN'),
    'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
    'TELEGRAM_CHAT_ID': os.getenv('TELEGRAM_CHAT_ID'),
}

print("=" * 60)
print("TrustStack Social Media Post Generator")
print("=" * 60)
print()

# Check optional variables
if not optional_vars['REPLICATE_API_TOKEN']:
    print("⚠️  REPLICATE_API_TOKEN not set - comic image generation will be skipped")
    print("   Set it in .env to enable comic image generation")
    print()

if not optional_vars['TELEGRAM_BOT_TOKEN'] or not optional_vars['TELEGRAM_CHAT_ID']:
    print("⚠️  Telegram credentials not set - approval workflow will be skipped")
    print("   Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env for approval workflow")
    print()

print("Attempting to import modules...")
try:
    from src.config import get_config
    from src.database import init_db, get_session
    from src.notion_client import NotionClient
    from src.openrouter_client import OpenrouterClient
    from src.mastodon_client import MastodonClient
    from src.article_fetcher import ArticleFetcher
    from src.enhanced_post_generator import EnhancedPostGenerator
    from src.manual_post_generator import ManualPostGenerator
    from src.telegram_bot import TelegramBot
    from src.approval_workflow import ApprovalWorkflow
    from src.image_handler import LogoHandler
    
    # Try to import ReplicateImageGenerator
    try:
        from src.replicate_image_generator import ReplicateImageGenerator
        REPLICATE_AVAILABLE = True
    except ImportError:
        REPLICATE_AVAILABLE = False
        print("⚠️  ReplicateImageGenerator not available (replicate package not installed)")
        print()
    
    print("✓ All modules imported successfully")
    print()
    
except ImportError as e:
    print(f"❌ Error importing modules: {e}")
    print()
    print("Please install dependencies:")
    print("  pip3 install -r requirements.txt")
    sys.exit(1)

# Initialize
print("Initializing components...")
config = get_config()
init_db()
db_session = get_session()

try:
    notion_client = NotionClient(
        config.notion_api_key,
        config.notion_page_id or "",
        database_id=getattr(config, 'notion_database_id', None),
    )
    openrouter_client = OpenrouterClient(config.openrouter_api_key, config.openrouter_model)
    mastodon_client = MastodonClient(config.mastodon_access_token, config.mastodon_api_base_url)
    article_fetcher = ArticleFetcher(
        rss_feeds=config.rss_feeds,
        keywords=config.article_keywords,
        max_articles_per_feed=config.article_settings.get('max_articles_per_feed', 20)
    )
    max_length = config.post_settings.get('max_length', 500)
    try:
        from src.rag import RAGRetriever
        rag_retriever = RAGRetriever()
    except ImportError:
        rag_retriever = None
    enhanced_generator = EnhancedPostGenerator(
        notion_client, openrouter_client, article_fetcher, max_length,
        rag_retriever=rag_retriever,
    )
    
    # Initialize logo handler
    logo_settings = config.logo_settings
    logo_handler = LogoHandler(
        logo_directory=logo_settings.get('directory', 'assets/logos'),
        default_logo=logo_settings.get('default_logo')
    )
    
    # Initialize image generator if available
    image_generator = None
    if REPLICATE_AVAILABLE and optional_vars['REPLICATE_API_TOKEN']:
        image_gen_settings = config.image_generation_settings
        if image_gen_settings.get('enabled', True):
            try:
                image_generator = ReplicateImageGenerator(
                    replicate_api_token=optional_vars['REPLICATE_API_TOKEN'],
                    openrouter_client=openrouter_client,
                    model=image_gen_settings.get('replicate_model', 'sundai-club/truststacksocial:b897202db67596183259c5dfaa424ddeb898cc5923934fe8afdd8e096c721517'),
                    trigger_word=image_gen_settings.get('trigger_word', 'truststack'),
                    model_type=image_gen_settings.get('model_type', 'schnell'),
                    num_inference_steps=image_gen_settings.get('num_inference_steps', 4),
                    guidance_scale=image_gen_settings.get('guidance_scale', 7.5),
                    style_suffix=image_gen_settings.get('style_suffix', 'cartoonish style, pastel colors'),
                    image_directory=image_gen_settings.get('image_directory', 'assets/generated_images')
                )
                print("✓ ReplicateImageGenerator initialized")
            except Exception as e:
                print(f"⚠️  Failed to initialize ReplicateImageGenerator: {e}")
                image_generator = None
    
    # Initialize Telegram bot and workflow if available
    telegram_bot = None
    approval_workflow = None
    if optional_vars['TELEGRAM_BOT_TOKEN'] and optional_vars['TELEGRAM_CHAT_ID']:
        telegram_settings = config.telegram_settings
        telegram_bot = TelegramBot(
            bot_token=optional_vars['TELEGRAM_BOT_TOKEN'],
            approval_chat_id=optional_vars['TELEGRAM_CHAT_ID']
        )
        approval_workflow = ApprovalWorkflow(
            telegram_bot=telegram_bot,
            mastodon_client=mastodon_client,
            logo_handler=logo_handler,
            approval_timeout_hours=telegram_settings.get('approval_timeout_hours', 24)
        )
        print("✓ Telegram bot and approval workflow initialized")
    
    # Initialize manual post generator
    manual_generator = ManualPostGenerator(
        enhanced_generator, approval_workflow, logo_handler, image_generator
    )
    
    print()
    print("=" * 60)
    print("Generating post with news, logo, and comic image...")
    print("=" * 60)
    print()
    
    # Generate post
    result = manual_generator.generate_and_queue_post(
        style="professional",
        temperature=0.7,
        max_articles=3,
        db_session=db_session
    )
    
    if result.get('success'):
        print()
        print("✓ Post generated successfully!")
        print()
        print(f"  Pending Post ID: {result['pending_post_id']}")
        print(f"  Style: {result['style']}")
        print(f"  Articles used: {result['articles_used']}")
        print(f"  Quotes included: {result['quotes_used']}")
        print(f"  Has logo: {result['has_logo']}")
        print(f"  Has comic image: {result.get('has_comic_image', False)}")
        print()
        
        if approval_workflow:
            print("✓ Post sent to Telegram for approval")
            print("  Check your Telegram chat to approve or reject the post")
        else:
            print("⚠️  Telegram not configured - post was created but not sent for approval")
            print("  You can manually approve it using:")
            print(f"    python main.py approve-post {result['pending_post_id']}")
        
        print()
        print("Post content preview:")
        print("-" * 60)
        print(result.get('content', 'N/A')[:200] + "...")
        print("-" * 60)
        
    else:
        print()
        print(f"❌ Error generating post: {result.get('error', 'Unknown error')}")
        sys.exit(1)
        
finally:
    db_session.close()
