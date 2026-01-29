"""
Approval workflow manager for pending posts
"""
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

import requests

from .database import PendingPost, PostApproval, Post, init_db, get_session

# Project root for resolving image paths when posting (approval may run from another cwd)
APP_ROOT = Path(__file__).resolve().parent.parent
from .telegram_bot import TelegramBot
from .mastodon_client import MastodonClient
from .image_handler import LogoHandler

logger = logging.getLogger(__name__)


class ApprovalWorkflow:
    """Manage the approval workflow for pending posts"""
    
    def __init__(
        self,
        telegram_bot: TelegramBot,
        mastodon_client: MastodonClient,
        logo_handler: LogoHandler,
        approval_timeout_hours: int = 24
    ):
        """
        Initialize approval workflow
        
        Args:
            telegram_bot: Telegram bot instance
            mastodon_client: Mastodon client instance
            logo_handler: Logo handler instance
            approval_timeout_hours: Hours before pending post expires
        """
        self.telegram_bot = telegram_bot
        self.mastodon_client = mastodon_client
        self.logo_handler = logo_handler
        self.approval_timeout_hours = approval_timeout_hours
        logger.info("Initialized ApprovalWorkflow")
    
    def create_pending_post(
        self,
        content: str,
        style: str,
        image_paths: Optional[List[str]] = None,
        article_ids: Optional[List[int]] = None,
        quotes: Optional[List[Dict[str, Any]]] = None,
        comic_media_url: Optional[str] = None,
        db_session: Optional[Session] = None
    ) -> PendingPost:
        """
        Create a pending post record
        
        Args:
            content: Post content
            style: Post style
            image_paths: List of image paths
            article_ids: List of article IDs used
            quotes: List of quotes used
            comic_media_url: Replicate output URL for comic (fallback when local file missing at approval)
            db_session: Database session
            
        Returns:
            Created PendingPost instance
        """
        if db_session is None:
            db_session = get_session()
            close_session = True
        else:
            close_session = False
        
        try:
            expires_at = datetime.utcnow() + timedelta(hours=self.approval_timeout_hours)
            
            pending_post = PendingPost(
                content=content,
                style=style,
                length=len(content),
                image_paths=image_paths or [],
                comic_media_url=comic_media_url,
                news_context=article_ids or [],
                news_quotes=quotes or [],
                status="pending",
                expires_at=expires_at
            )
            
            db_session.add(pending_post)
            db_session.commit()
            db_session.refresh(pending_post)
            
            logger.info("Created pending post %s with image_paths: %s", pending_post.id, image_paths or [])
            return pending_post
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error creating pending post: {e}")
            raise
        finally:
            if close_session:
                db_session.close()
    
    def send_for_approval(
        self,
        pending_post: PendingPost,
        articles: Optional[List[Dict[str, Any]]] = None,
        db_session: Optional[Session] = None
    ) -> bool:
        """
        Send pending post to Telegram for approval
        
        Args:
            pending_post: PendingPost instance
            articles: Optional list of article details
            db_session: Database session
            
        Returns:
            True if successful
        """
        try:
            # Prepare image paths (resolve relative to APP_ROOT so Telegram can open files)
            raw = pending_post.image_paths or []
            image_paths = []
            for r in raw:
                p = Path(str(r).strip())
                if not p.is_absolute():
                    p = APP_ROOT / p
                if p.exists():
                    image_paths.append(str(p))
            
            # Prepare articles and quotes
            quotes = pending_post.news_quotes or []
            
            # Send to Telegram
            message_id = self.telegram_bot.send_post_for_approval(
                pending_post_id=pending_post.id,
                content=pending_post.content,
                style=pending_post.style,
                image_paths=image_paths if image_paths else None,
                articles=articles,
                quotes=quotes
            )
            
            if message_id:
                # Update pending post with Telegram message ID
                if db_session is None:
                    db_session = get_session()
                    close_session = True
                else:
                    close_session = False
                
                try:
                    pending_post.telegram_message_id = str(message_id)
                    pending_post.telegram_chat_id = self.telegram_bot.approval_chat_id
                    db_session.commit()
                    logger.info(f"Sent pending post {pending_post.id} for approval (message ID: {message_id})")
                    return True
                except Exception as e:
                    logger.error(f"Error updating pending post: {e}")
                    db_session.rollback()
                    return False
                finally:
                    if close_session:
                        db_session.close()
            else:
                logger.error(f"Failed to send pending post {pending_post.id} to Telegram")
                return False
                
        except Exception as e:
            logger.error(f"Error sending for approval: {e}")
            return False
    
    def process_approval(
        self,
        pending_post_id: int,
        telegram_user_id: Optional[str] = None,
        telegram_username: Optional[str] = None,
        db_session: Optional[Session] = None,
        skip_telegram_edit: bool = False
    ) -> bool:
        """
        Process approval action

        Args:
            pending_post_id: Pending post ID
            telegram_user_id: Telegram user ID who approved
            telegram_username: Telegram username who approved
            db_session: Database session
            skip_telegram_edit: If True, do not edit the Telegram message (caller will edit)

        Returns:
            True if successful
        """
        if db_session is None:
            db_session = get_session()
            close_session = True
        else:
            close_session = False
        
        try:
            pending_post = db_session.query(PendingPost).filter(PendingPost.id == pending_post_id).first()
            
            if not pending_post:
                logger.error(f"Pending post {pending_post_id} not found")
                return False
            
            if pending_post.status != "pending":
                logger.warning(f"Pending post {pending_post_id} is not in pending status: {pending_post.status}")
                return False
            
            # Update pending post status
            pending_post.status = "approved"
            pending_post.approved_at = datetime.utcnow()
            
            # Create approval record
            approval = PostApproval(
                pending_post_id=pending_post_id,
                action="approve",
                telegram_user_id=telegram_user_id,
                telegram_username=telegram_username
            )
            db_session.add(approval)
            
            # Post to Mastodon: resolve and validate image paths so comic/logo are found
            raw_paths = pending_post.image_paths
            if isinstance(raw_paths, str):
                try:
                    raw_paths = json.loads(raw_paths)
                except (json.JSONDecodeError, TypeError):
                    raw_paths = []
            if not isinstance(raw_paths, list):
                raw_paths = list(raw_paths) if raw_paths else []
            raw_paths = [str(x).strip() for x in raw_paths if x is not None]
            # Diagnostics: log what we got from DB
            logger.info(
                "Pending post image_paths from DB: type=%s, count=%s, sample=%s",
                type(raw_paths).__name__, len(raw_paths),
                raw_paths[:2] if raw_paths else None
            )
            image_paths = []
            for raw_path in raw_paths:
                p = Path(str(raw_path).strip())
                is_abs = p.is_absolute()
                if not is_abs:
                    p = APP_ROOT / raw_path
                exists = p.exists()
                logger.info("Image path: raw=%s absolute=%s exists=%s", raw_path, is_abs, exists)
                if exists:
                    image_paths.append(str(p))
                else:
                    logger.warning("Image path does not exist at post time, skipping: %s", p)
            if raw_paths and len(image_paths) < len(raw_paths):
                logger.warning("Only %d/%d image paths exist; posting with available images", len(image_paths), len(raw_paths))
            if raw_paths and len(image_paths) == 0:
                logger.warning(
                    "No image paths exist at approval time. Comic/logo may be missing because this process cannot see the files "
                    "(e.g. different machine or cwd). Run generation from project root and approval on the same machine."
                )
            # URL fallback: if local comic (or other images) missing and we have comic_media_url, download and use it
            temp_paths_to_clean = []
            comic_url = getattr(pending_post, "comic_media_url", None)
            if comic_url and (not image_paths or (raw_paths and len(image_paths) < len(raw_paths))):
                try:
                    logger.info("Comic local path missing; downloading from comic_media_url")
                    resp = requests.get(comic_url, timeout=30)
                    resp.raise_for_status()
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".webp") as f:
                        f.write(resp.content)
                        temp_path = f.name
                    temp_paths_to_clean.append(temp_path)
                    image_paths.insert(0, temp_path)  # comic first
                    logger.info("Downloaded comic from URL for Mastodon upload")
                except Exception as e:
                    logger.warning("Failed to download comic from comic_media_url: %s", e)
            if image_paths:
                logger.info("Posting to Mastodon with %d image(s): %s", len(image_paths), image_paths)
            
            try:
                if image_paths:
                    result = self.mastodon_client.post_with_media(
                        content=pending_post.content,
                        image_paths=image_paths,
                        visibility="public"
                    )
                else:
                    result = self.mastodon_client.post(
                        content=pending_post.content,
                        visibility="public"
                    )
                
                # Create regular Post record
                regular_post = Post(
                    content=pending_post.content,
                    style=pending_post.style,
                    length=pending_post.length,
                    generated_at=pending_post.generated_at,
                    posted=True,
                    posted_at=datetime.utcnow(),
                    mastodon_url=result.get('url'),
                    mastodon_id=str(result.get('id', ''))
                )
                db_session.add(regular_post)
                
                logger.info(f"Posted pending post {pending_post_id} to Mastodon: {result.get('url')}")
                
            except Exception as e:
                logger.error(f"Error posting to Mastodon: {e}")
                # Still mark as approved even if posting fails
                # The post can be manually posted later
            finally:
                for p in temp_paths_to_clean:
                    try:
                        os.unlink(p)
                    except OSError:
                        pass
            
            # Update Telegram message (skip when caller, e.g. bot server, will edit)
            if not skip_telegram_edit and pending_post.telegram_message_id:
                try:
                    self.telegram_bot.edit_message_after_action(
                        int(pending_post.telegram_message_id),
                        "approve",
                        pending_post_id
                    )
                except Exception as e:
                    logger.warning(f"Error editing Telegram message: {e}")

            db_session.commit()
            logger.info(f"Approved pending post {pending_post_id}")
            return True
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error processing approval: {e}")
            return False
        finally:
            if close_session:
                db_session.close()
    
    def process_rejection(
        self,
        pending_post_id: int,
        rejection_reason: Optional[str] = None,
        telegram_user_id: Optional[str] = None,
        telegram_username: Optional[str] = None,
        db_session: Optional[Session] = None
    ) -> bool:
        """
        Process rejection action (archive for review)
        
        Args:
            pending_post_id: Pending post ID
            rejection_reason: Optional reason for rejection
            telegram_user_id: Telegram user ID who rejected
            telegram_username: Telegram username who rejected
            db_session: Database session
            
        Returns:
            True if successful
        """
        if db_session is None:
            db_session = get_session()
            close_session = True
        else:
            close_session = False
        
        try:
            pending_post = db_session.query(PendingPost).filter(PendingPost.id == pending_post_id).first()
            
            if not pending_post:
                logger.error(f"Pending post {pending_post_id} not found")
                return False
            
            if pending_post.status != "pending":
                logger.warning(f"Pending post {pending_post_id} is not in pending status: {pending_post.status}")
                return False
            
            # Update pending post status to archived
            pending_post.status = "archived"
            pending_post.rejected_at = datetime.utcnow()
            pending_post.archived_at = datetime.utcnow()
            pending_post.rejection_reason = rejection_reason
            
            # Create approval record
            approval = PostApproval(
                pending_post_id=pending_post_id,
                action="reject",
                telegram_user_id=telegram_user_id,
                telegram_username=telegram_username,
                notes=rejection_reason
            )
            db_session.add(approval)
            
            # Update Telegram message
            if pending_post.telegram_message_id:
                try:
                    self.telegram_bot.edit_message_after_action(
                        int(pending_post.telegram_message_id),
                        "reject",
                        pending_post_id
                    )
                except Exception as e:
                    logger.warning(f"Error editing Telegram message: {e}")
            
            db_session.commit()
            logger.info(f"Rejected and archived pending post {pending_post_id}")
            return True
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error processing rejection: {e}")
            return False
        finally:
            if close_session:
                db_session.close()
    
    def check_expired_posts(self, db_session: Optional[Session] = None) -> int:
        """
        Check and auto-reject expired pending posts
        
        Args:
            db_session: Database session
            
        Returns:
            Number of expired posts processed
        """
        if db_session is None:
            db_session = get_session()
            close_session = True
        else:
            close_session = False
        
        try:
            now = datetime.utcnow()
            expired_posts = db_session.query(PendingPost).filter(
                PendingPost.status == "pending",
                PendingPost.expires_at < now
            ).all()
            
            count = 0
            for pending_post in expired_posts:
                self.process_rejection(
                    pending_post.id,
                    rejection_reason="Expired (auto-rejected)",
                    db_session=db_session
                )
                count += 1
            
            if count > 0:
                logger.info(f"Auto-rejected {count} expired pending posts")
            
            return count
            
        except Exception as e:
            logger.error(f"Error checking expired posts: {e}")
            return 0
        finally:
            if close_session:
                db_session.close()
