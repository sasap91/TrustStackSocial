#!/usr/bin/env python3
"""
Telegram bot server for handling approval callbacks
"""
import asyncio
import json
import os
import sys
import logging
import time
from pathlib import Path
from telegram import Update

# #region agent log
def _debug_log(location: str, message: str, data: dict, hypothesis_id: str):
    try:
        log_path = Path(__file__).resolve().parent / ".cursor" / "debug.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.open("a").write(json.dumps({"timestamp": int(time.time() * 1000), "location": location, "message": message, "data": data, "sessionId": "debug-session", "hypothesisId": hypothesis_id}) + "\n")
    except Exception:
        pass
# #endregion

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_config
from src.database import get_session, init_db
from src.telegram_bot import TelegramBot
from src.mastodon_client import MastodonClient
from src.approval_workflow import ApprovalWorkflow
from src.image_handler import LogoHandler
from src.utils import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Global state for feedback collection
feedback_state = {}  # pending_post_id -> waiting_for_feedback


async def _edit_message_after_action(query, text: str):
    """Edit the callback message and remove inline keyboard so confirmation shows."""
    try:
        await query.edit_message_text(text=text, reply_markup=None)
    except Exception as e:
        logger.exception("Failed to edit Telegram message after action: %s", e)
        raise


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline buttons"""
    query = update.callback_query
    user = query.from_user
    callback_data = query.data

    # #region agent log
    _debug_log("telegram_bot_server.py:handle_callback:entry", "callback received", {"callback_data": callback_data}, "A")
    # #endregion

    logger.info(f"Received callback from @{user.username}: {callback_data}")

    # Answer immediately so Telegram shows feedback and doesn't timeout
    if callback_data.startswith("approve_"):
        await query.answer("Posting to Mastodon…")
    else:
        await query.answer()
    
    # Parse callback data (format: "approve_123" or "reject_123")
    if callback_data.startswith("approve_"):
        action = "approve"
        pending_post_id = int(callback_data.split("_")[1])
    elif callback_data.startswith("reject_"):
        action = "reject"
        pending_post_id = int(callback_data.split("_")[1])
    else:
        await query.edit_message_text("Unknown action", reply_markup=None)
        return
    
    # Clear feedback state if exists
    if pending_post_id in feedback_state:
        del feedback_state[pending_post_id]
    
    # Initialize components
    config = get_config()
    init_db()
    db_session = get_session()

    try:
        # Initialize clients
        mastodon_client = MastodonClient(
            config.mastodon_access_token,
            config.mastodon_api_base_url
        )
        logo_handler = LogoHandler(
            logo_directory=config.logo_settings.get('directory', 'assets/logos')
        )
        telegram_bot = TelegramBot(
            bot_token=config.telegram_bot_token,
            approval_chat_id=config.telegram_chat_id
        )

        approval_workflow = ApprovalWorkflow(
            telegram_bot=telegram_bot,
            mastodon_client=mastodon_client,
            logo_handler=logo_handler
        )

        # Process action
        if action == "approve":
            # #region agent log
            _debug_log("telegram_bot_server.py:handle_callback:before_to_thread", "calling process_approval", {"pending_post_id": pending_post_id}, "E")
            # #endregion
            # Run in thread so event loop stays responsive and Telegram edit runs after
            try:
                success = await asyncio.to_thread(
                    approval_workflow.process_approval,
                    pending_post_id,
                    str(user.id),
                    user.username or "",
                    None,
                    True
                )
            except Exception as to_thread_err:
                # #region agent log
                _debug_log("telegram_bot_server.py:handle_callback:to_thread_raised", "to_thread exception", {"error": str(to_thread_err)}, "C")
                # #endregion
                raise
            # #region agent log
            _debug_log("telegram_bot_server.py:handle_callback:after_process_approval", "process_approval returned", {"success": success}, "B")
            # #endregion

            if success:
                # #region agent log
                _debug_log("telegram_bot_server.py:handle_callback:before_edit_success", "editing message (success)", {"pending_post_id": pending_post_id}, "D")
                # #endregion
                await _edit_message_after_action(
                    query,
                    f"✅ You approved this post.\n\nPost {pending_post_id} has been posted to Mastodon."
                )
                # #region agent log
                _debug_log("telegram_bot_server.py:handle_callback:after_edit_success", "edit done", {}, "D")
                # #endregion
            else:
                # #region agent log
                _debug_log("telegram_bot_server.py:handle_callback:before_edit_fail", "editing message (fail)", {"pending_post_id": pending_post_id}, "D")
                # #endregion
                await _edit_message_after_action(
                    query,
                    f"❌ Failed to post to Mastodon.\n\nPost {pending_post_id} could not be published. "
                    f"Check Mastodon credentials and try again or use CLI/API."
                )
                # #region agent log
                _debug_log("telegram_bot_server.py:handle_callback:after_edit_fail", "edit done", {}, "D")
                # #endregion

        elif action == "reject":
            # Ask for feedback reason (don't complete rejection yet)
            feedback_state[pending_post_id] = True
            await query.edit_message_text(
                f"❌ You rejected this post.\n\n"
                f"Post {pending_post_id} has been rejected.\n\n"
                f"Please reply with the reason for rejection.\n"
                f"This feedback helps improve future posts.\n\n"
                f"Examples: 'Too promotional', 'Wrong tone', 'Not relevant'",
                reply_markup=None
            )
            # Don't complete rejection yet - wait for feedback in handle_feedback_message
            db_session.close()
            return
                
    except Exception as e:
        # #region agent log
        _debug_log("telegram_bot_server.py:handle_callback:except", "callback exception", {"error": str(e)}, "C")
        # #endregion
        logger.error(f"Error processing callback: {e}")
        try:
            await query.edit_message_text(
                f"❌ Error processing request: {str(e)}\n\nPlease try again or use CLI/API.",
                reply_markup=None
            )
        except Exception as edit_err:
            # #region agent log
            _debug_log("telegram_bot_server.py:handle_callback:edit_after_error_failed", "edit after error failed", {"edit_err": str(edit_err)}, "D")
            # #endregion
            logger.exception("Could not edit message after error: %s", edit_err)
    finally:
        db_session.close()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    await update.message.reply_text(
        "🤖 TrustStackSocial Telegram Bot\n\n"
        "This bot handles post approval requests.\n"
        "Use the inline buttons to approve or reject posts."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    await update.message.reply_text(
        "📖 Help\n\n"
        "This bot receives post approval requests.\n"
        "Click the inline buttons (✅ Approve / ❌ Reject) to take action on pending posts.\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message"
    )


async def handle_feedback_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages as feedback for rejected posts"""
    if not update.message or not update.message.text:
        return
    
    user = update.message.from_user
    feedback_text = update.message.text
    
    # Check if this is feedback for a pending post
    pending_post_id = None
    for post_id, waiting in list(feedback_state.items()):
        if waiting:
            pending_post_id = post_id
            break
    
    if pending_post_id is None:
        # Not waiting for feedback, ignore
        return
    
    # Clear feedback state immediately to prevent duplicate processing
    if pending_post_id in feedback_state:
        del feedback_state[pending_post_id]
    
    # Process rejection with feedback
    config = get_config()
    init_db()
    db_session = get_session()
    
    try:
        mastodon_client = MastodonClient(
            config.mastodon_access_token,
            config.mastodon_api_base_url
        )
        logo_handler = LogoHandler(
            logo_directory=config.logo_settings.get('directory', 'assets/logos')
        )
        telegram_bot = TelegramBot(
            bot_token=config.telegram_bot_token,
            approval_chat_id=config.telegram_chat_id
        )
        
        approval_workflow = ApprovalWorkflow(
            telegram_bot=telegram_bot,
            mastodon_client=mastodon_client,
            logo_handler=logo_handler
        )
        
        success = approval_workflow.process_rejection(
            pending_post_id,
            rejection_reason=feedback_text,
            telegram_user_id=str(user.id),
            telegram_username=user.username,
            db_session=db_session
        )
        
        if success:
            await update.message.reply_text(
                f"📝 Feedback recorded!\n\n"
                f"Reason: {feedback_text}\n\n"
                f"Post {pending_post_id} has been archived for review."
            )
            # Clear feedback state
            if pending_post_id in feedback_state:
                del feedback_state[pending_post_id]
        else:
            await update.message.reply_text(
                f"❌ Failed to process rejection. Please try again or use CLI/API."
            )
            
    except Exception as e:
        logger.error(f"Error processing feedback: {e}")
        await update.message.reply_text(
            f"❌ Error processing feedback: {str(e)}"
        )
    finally:
        db_session.close()


def main():
    """Main function to run the Telegram bot"""
    # Get configuration
    config = get_config()
    
    if not config.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set in environment variables")
        sys.exit(1)
    
    # Create application
    application = Application.builder().token(config.telegram_bot_token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback_message))
    
    # Initialize database
    init_db()
    
    logger.info("Starting Telegram bot server...")
    logger.info("Bot is ready to receive callbacks")
    
    # Run bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
