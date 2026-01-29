"""
Telegram bot integration for post approval workflow
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.error import TelegramError

# Note: IPv4 forcing is handled at socket level in main.py
# httpx (used by python-telegram-bot) will inherit IPv4-only behavior

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot for sending approval requests"""
    
    def __init__(self, bot_token: str, approval_chat_id: str):
        """
        Initialize Telegram bot
        
        Args:
            bot_token: Telegram bot token
            approval_chat_id: Chat ID for sending approval requests
        """
        self.bot_token = bot_token
        self.approval_chat_id = approval_chat_id
        self.bot = Bot(token=bot_token)
        logger.info("Initialized TelegramBot")
    
    def format_post_preview(
        self,
        content: str,
        style: str,
        articles: Optional[List[Dict[str, Any]]] = None,
        quotes: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Format post preview for Telegram
        
        Args:
            content: Post content
            style: Post style
            articles: List of articles used
            quotes: List of quotes used
            
        Returns:
            Formatted preview text
        """
        preview = f"📝 *New Post for Approval*\n\n"
        preview += f"*Style:* {style}\n"
        preview += f"*Length:* {len(content)} chars\n\n"
        preview += f"*Content:*\n{content}\n\n"
        
        if articles:
            preview += f"*Articles Used:* {len(articles)}\n"
            for i, article in enumerate(articles[:3], 1):
                preview += f"{i}. {article.get('title', 'Unknown')[:50]}...\n"
        
        if quotes:
            preview += f"\n*Quotes Included:*\n"
            for i, quote in enumerate(quotes[:2], 1):
                preview += f"{i}. \"{quote.get('quote', quote.get('text', ''))[:80]}...\"\n"
        
        return preview
    
    def send_post_for_approval(
        self,
        pending_post_id: int,
        content: str,
        style: str,
        image_paths: Optional[List[str]] = None,
        articles: Optional[List[Dict[str, Any]]] = None,
        quotes: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[int]:
        """
        Send post preview to Telegram for approval
        
        Args:
            pending_post_id: ID of pending post
            content: Post content
            style: Post style
            image_paths: Optional list of image paths
            articles: Optional list of articles used
            quotes: Optional list of quotes used
            
        Returns:
            Telegram message ID if successful, None otherwise
        """
        async def _send():
            try:
                # Format preview text
                preview_text = self.format_post_preview(content, style, articles, quotes)
                
                # Create inline keyboard: Reject left, Approve right (primary action)
                keyboard = [
                    [
                        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{pending_post_id}"),
                        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{pending_post_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Send message with images if available
                if image_paths and len(image_paths) > 0:
                    # Read image files as bytes to avoid file handle closure issues
                    media_group = []
                    for i, image_path in enumerate(image_paths[:10]):  # Telegram limit: 10 images
                        try:
                            with open(image_path, "rb") as f:
                                image_bytes = f.read()
                            
                            if i == 0:
                                # First image with caption
                                media_group.append(
                                    InputMediaPhoto(
                                        media=image_bytes,
                                        caption=preview_text,
                                        parse_mode='Markdown'
                                    )
                                )
                            else:
                                # Other images without caption
                                media_group.append(
                                    InputMediaPhoto(media=image_bytes)
                                )
                        except Exception as e:
                            logger.warning(f"Error adding image {image_path} to media group: {e}")
                            continue
                    
                    if media_group:
                        # Send media group
                        messages = await self.bot.send_media_group(
                            chat_id=self.approval_chat_id,
                            media=media_group
                        )
                        message_id = messages[0].message_id if messages else None
                        
                        # Send approval buttons as separate message
                        if message_id:
                            button_message = await self.bot.send_message(
                                chat_id=self.approval_chat_id,
                                text="Choose an action:",
                                reply_markup=reply_markup
                            )
                            return button_message.message_id
                else:
                    # Send text message with buttons
                    message = await self.bot.send_message(
                        chat_id=self.approval_chat_id,
                        text=preview_text,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                    return message.message_id
                
                return None
                
            except TelegramError as e:
                logger.error(f"Telegram error sending approval request: {e}")
                return None
            except Exception as e:
                logger.error(f"Error sending approval request: {e}")
                return None
        
        # Run async code from sync CLI
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_send())
        else:
            # If already in an event loop (rare for CLI), use run_until_complete
            return loop.run_until_complete(_send())
    
    def edit_message_after_action(
        self,
        message_id: int,
        action: str,
        pending_post_id: int
    ) -> bool:
        """
        Edit message after approval/rejection action
        
        Args:
            message_id: Telegram message ID
            action: Action taken (approve/reject)
            pending_post_id: Pending post ID
            
        Returns:
            True if successful
        """
        async def _edit():
            try:
                status_text = "✅ Approved" if action == "approve" else "❌ Rejected"
                new_text = f"{status_text}\n\nPost ID: {pending_post_id}\nAction taken at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                await self.bot.edit_message_text(
                    chat_id=self.approval_chat_id,
                    message_id=message_id,
                    text=new_text
                )
                return True
                
            except Exception as e:
                logger.error(f"Error editing message: {e}")
                return False
        
        # Run async code from sync CLI
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_edit())
        else:
            return loop.run_until_complete(_edit())
    
    def send_notification(
        self,
        message: str,
        parse_mode: Optional[str] = "Markdown"
    ) -> bool:
        """
        Send a notification message
        
        Args:
            message: Message text
            parse_mode: Parse mode (Markdown, HTML, or None)
            
        Returns:
            True if successful
        """
        async def _send():
            try:
                await self.bot.send_message(
                    chat_id=self.approval_chat_id,
                    text=message,
                    parse_mode=parse_mode
                )
                return True
            except Exception as e:
                logger.error(f"Error sending notification: {e}")
                return False
        
        # Run async code from sync CLI
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_send())
        else:
            return loop.run_until_complete(_send())
