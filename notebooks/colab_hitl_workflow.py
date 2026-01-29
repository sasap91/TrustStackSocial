"""
Colab-compatible HITL workflow script
Can be imported and used in Google Colab notebooks
"""
import os
import sys
import asyncio
from pathlib import Path
from typing import Optional, Tuple

# Add parent directory to path for imports
if '/content' in str(Path.cwd()) or 'google.colab' in str(sys.modules):
    # Running in Colab
    parent_dir = Path.cwd()
else:
    parent_dir = Path(__file__).parent.parent

sys.path.insert(0, str(parent_dir))

try:
    from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters, ContextTypes
    from src.config import get_config
    from src.database import get_session, init_db
    from src.telegram_bot import TelegramBot
    from src.mastodon_client import MastodonClient
    from src.approval_workflow import ApprovalWorkflow
    from src.image_handler import LogoHandler
    from src.manual_post_generator import ManualPostGenerator
    from src.enhanced_post_generator import EnhancedPostGenerator
    from src.article_fetcher import ArticleFetcher
    from src.notion_client import NotionClient
    from src.openrouter_client import OpenrouterClient
except ImportError as e:
    print(f"Warning: Could not import some modules: {e}")
    print("Make sure all dependencies are installed:")
    print("!pip install python-telegram-bot python-dotenv sqlalchemy")


# Global state for approval workflow
approval_state = {
    'pending_post_id': None,
    'decision_result': None,
    'feedback_reason': None,
    'waiting_for_feedback': False
}
approval_event = asyncio.Event()


async def send_simple_message(text: str, bot_token: str, chat_id: str):
    """Send a basic text message to Telegram."""
    bot = Bot(token=bot_token)
    message = await bot.send_message(
        chat_id=int(chat_id),
        text=text,
    )
    print(f"✅ Message sent! ID: {message.message_id}")
    return message


async def send_message_with_buttons(text: str, bot_token: str, chat_id: str, callback_data_prefix: str = ""):
    """Send a message with Approve/Reject buttons."""
    bot = Bot(token=bot_token)

    # Create the keyboard with two buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"{callback_data_prefix}approve"),
            InlineKeyboardButton("❌ Reject", callback_data=f"{callback_data_prefix}reject"),
        ]
    ])

    message = await bot.send_message(
        chat_id=int(chat_id),
        text=text,
        reply_markup=keyboard,
    )
    print(f"✅ Message with buttons sent! ID: {message.message_id}")
    return message


async def wait_for_approval_with_feedback(
    post_content: str,
    bot_token: str,
    chat_id: str,
    pending_post_id: Optional[int] = None
) -> Tuple[str, Optional[str]]:
    """
    Send post for approval. If rejected, collect the reason.
    Returns (decision, rejection_reason).
    """
    global approval_state, approval_event
    
    async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
        global approval_state
        query = update.callback_query
        await query.answer()

        if query.data.endswith("approve"):
            approval_state['decision_result'] = "approve"
            await query.edit_message_text(f"✅ APPROVED\n\n{post_content}")
            approval_event.set()
        elif query.data.endswith("reject"):
            approval_state['decision_result'] = "reject"
            approval_state['waiting_for_feedback'] = True
            await query.edit_message_text(
                "❌ REJECTED\n\n"
                "Please reply with the reason for rejection.\n"
                "This feedback helps improve future posts.\n\n"
                "Examples: 'Too promotional' or 'Wrong tone'"
            )

    async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
        global approval_state
        if not approval_state['waiting_for_feedback']:
            return

        approval_state['feedback_reason'] = update.message.text
        approval_state['waiting_for_feedback'] = False
        await update.message.reply_text(
            f"📝 Feedback recorded!\n\nReason: {approval_state['feedback_reason']}"
        )
        approval_event.set()

    # Reset state
    approval_state['pending_post_id'] = pending_post_id
    approval_state['decision_result'] = None
    approval_state['feedback_reason'] = None
    approval_state['waiting_for_feedback'] = False
    approval_event.clear()

    # Send the post
    callback_prefix = f"{pending_post_id}_" if pending_post_id else ""
    await send_message_with_buttons(
        f"📝 New Post for Approval\n\n{post_content}\n\nCharacters: {len(post_content)}",
        bot_token,
        chat_id,
        callback_data_prefix=callback_prefix
    )
    print("📱 Sent to Telegram. Waiting for approval...")

    # Set up listeners
    app = Application.builder().token(bot_token).build()
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Wait for completion
    try:
        await asyncio.wait_for(approval_event.wait(), timeout=300)  # 5 minute timeout
    except asyncio.TimeoutError:
        print("⏱️ Timeout waiting for approval")
        approval_state['decision_result'] = "timeout"
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

    return approval_state['decision_result'], approval_state['feedback_reason']


async def generate_and_approve_post(
    style: str = "professional",
    temperature: float = 0.7,
    max_articles: int = 3
) -> dict:
    """
    Complete workflow: Generate post and get approval.
    Returns dict with result information.
    """
    try:
        # Get configuration
        config = get_config()
        
        # Initialize database
        init_db()
        db_session = get_session()
        
        # Initialize clients
        notion_client = NotionClient(config.notion_api_key, config.notion_page_id)
        openrouter_client = OpenrouterClient(config.openrouter_api_key, config.openrouter_model)
        mastodon_client = MastodonClient(config.mastodon_access_token, config.mastodon_api_base_url)
        
        # Initialize article fetcher
        article_fetcher = ArticleFetcher(
            rss_feeds=config.rss_feeds,
            keywords=config.article_keywords,
            max_articles_per_feed=config.article_settings.get('max_articles_per_feed', 20)
        )
        
        # Initialize enhanced generator
        max_length = config.post_settings.get('max_length', 500)
        enhanced_generator = EnhancedPostGenerator(
            notion_client, openrouter_client, article_fetcher, max_length
        )
        
        # Initialize logo handler
        logo_handler = LogoHandler(
            logo_directory=config.logo_settings.get('directory', 'assets/logos')
        )
        
        # Initialize Telegram bot
        telegram_bot = TelegramBot(
            bot_token=config.telegram_bot_token,
            approval_chat_id=config.telegram_chat_id
        )
        
        # Initialize approval workflow
        approval_workflow = ApprovalWorkflow(
            telegram_bot=telegram_bot,
            mastodon_client=mastodon_client,
            logo_handler=logo_handler
        )
        
        # Initialize manual post generator
        manual_generator = ManualPostGenerator(
            enhanced_generator, approval_workflow, logo_handler
        )
        
        # Generate post
        print("🤖 Generating post with news...")
        result = manual_generator.generate_and_queue_post(
            style=style,
            temperature=temperature,
            max_articles=max_articles,
            db_session=db_session
        )
        
        if not result.get('success'):
            return {
                'success': False,
                'error': result.get('error', 'Failed to generate post')
            }
        
        pending_post_id = result['pending_post_id']
        post_content = result['content']
        
        # Wait for approval with feedback
        print(f"\n📱 Post {pending_post_id} sent for approval...")
        decision, reason = await wait_for_approval_with_feedback(
            post_content,
            config.telegram_bot_token,
            config.telegram_chat_id,
            pending_post_id=pending_post_id
        )
        
        db_session.close()
        
        if decision == "approve":
            # Post was already posted by approval_workflow
            return {
                'success': True,
                'decision': 'approved',
                'pending_post_id': pending_post_id,
                'message': 'Post approved and published to Mastodon'
            }
        elif decision == "reject":
            return {
                'success': True,
                'decision': 'rejected',
                'pending_post_id': pending_post_id,
                'rejection_reason': reason,
                'message': 'Post rejected and archived'
            }
        else:
            return {
                'success': False,
                'decision': decision,
                'error': 'Timeout or error during approval'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


# Example usage in Colab:
# 
# # Set environment variables
# import os
# os.environ["TELEGRAM_BOT_TOKEN"] = "your_token"
# os.environ["TELEGRAM_CHAT_ID"] = "your_chat_id"
# os.environ["OPENROUTER_API_KEY"] = "your_key"
# # ... other env vars
#
# # Run the workflow
# result = await generate_and_approve_post(style="professional")
# print(result)
