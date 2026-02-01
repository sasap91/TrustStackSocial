"""
Mastodon API client for posting social media content
"""
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
from mastodon import Mastodon

logger = logging.getLogger(__name__)

# Project root for resolving relative image paths (e.g. when approval runs from another cwd)
APP_ROOT = Path(__file__).resolve().parent.parent


class MastodonClient:
    """Client for posting to Mastodon"""
    
    def __init__(self, access_token: str, api_base_url: str = "https://mastodon.social"):
        """
        Initialize Mastodon client
        
        Args:
            access_token: Mastodon access token
            api_base_url: Mastodon instance URL
        """
        self.access_token = access_token
        self.api_base_url = api_base_url
        
        self.client = Mastodon(
            access_token=access_token,
            api_base_url=api_base_url
        )
        
        logger.info(f"Initialized Mastodon client for {api_base_url}")
        
        # Verify credentials (non-blocking - will fail gracefully if network unavailable)
        try:
            account = self.client.account_verify_credentials()
            logger.info(f"Logged in as: @{account['username']}")
        except Exception as e:
            logger.warning(f"Could not verify Mastodon credentials (network may be unavailable): {e}")
            logger.info("Continuing anyway - credentials will be verified when posting")
    
    def post(
        self,
        content: str,
        visibility: str = "public",
        sensitive: bool = False,
        spoiler_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Post content to Mastodon
        
        Args:
            content: Post content
            visibility: Visibility setting (public, unlisted, private, direct)
            sensitive: Mark as sensitive content
            spoiler_text: Content warning text
            
        Returns:
            Posted status information
        """
        try:
            logger.info(f"Posting to Mastodon ({len(content)} chars)")
            
            status = self.client.status_post(
                status=content,
                visibility=visibility,
                sensitive=sensitive,
                spoiler_text=spoiler_text
            )
            
            logger.info(f"Successfully posted. Status ID: {status['id']}")
            logger.info(f"URL: {status['url']}")
            
            return {
                'id': status['id'],
                'url': status['url'],
                'created_at': status['created_at'].isoformat(),
                'visibility': visibility,
                'favourites_count': status.get('favourites_count', 0),
                'reblogs_count': status.get('reblogs_count', 0)
            }
            
        except Exception as e:
            logger.error(f"Error posting to Mastodon: {e}")
            raise
    
    def post_thread(
        self,
        posts: list,
        visibility: str = "public",
        delay_seconds: int = 2
    ) -> list:
        """
        Post a thread of related posts
        
        Args:
            posts: List of post contents
            visibility: Visibility setting
            delay_seconds: Delay between posts
            
        Returns:
            List of posted status information
        """
        import time
        
        results = []
        in_reply_to_id = None
        
        for i, content in enumerate(posts):
            logger.info(f"Posting thread {i+1}/{len(posts)}")
            
            try:
                status = self.client.status_post(
                    status=content,
                    visibility=visibility,
                    in_reply_to_id=in_reply_to_id
                )
                
                results.append({
                    'id': status['id'],
                    'url': status['url'],
                    'created_at': status['created_at'].isoformat()
                })
                
                # Set reply ID for next post in thread
                in_reply_to_id = status['id']
                
                # Delay before next post
                if i < len(posts) - 1:
                    time.sleep(delay_seconds)
                
            except Exception as e:
                logger.error(f"Error posting thread item {i+1}: {e}")
                break
        
        logger.info(f"Posted thread with {len(results)} posts")
        return results
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get current account information
        
        Returns:
            Account information
        """
        try:
            account = self.client.account_verify_credentials()
            return {
                'id': account['id'],
                'username': account['username'],
                'display_name': account['display_name'],
                'followers_count': account['followers_count'],
                'following_count': account['following_count'],
                'statuses_count': account['statuses_count'],
                'url': account['url']
            }
        except Exception as e:
            logger.error(f"Error fetching account info: {e}")
            raise
    
    def preview_post(self, content: str) -> Dict[str, Any]:
        """
        Preview a post without actually posting it
        
        Args:
            content: Post content to preview
            
        Returns:
            Preview information
        """
        return {
            'content': content,
            'length': len(content),
            'max_length': 500,  # Default Mastodon limit
            'valid': len(content) <= 500,
            'preview_url': f"{self.api_base_url}/web/statuses/new"
        }
    
    def delete_status(self, status_id: str) -> bool:
        """
        Delete a posted status
        
        Args:
            status_id: ID of status to delete
            
        Returns:
            True if successful
        """
        try:
            self.client.status_delete(status_id)
            logger.info(f"Deleted status: {status_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting status: {e}")
            return False
    
    def search_posts(
        self,
        query: str,
        limit: int = 5,
        account_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for posts on Mastodon using hashtag timeline
        
        Args:
            query: Hashtag to search for (without #)
            limit: Maximum number of results
            account_id: Optional account ID to exclude own posts
            
        Returns:
            List of matching posts
        """
        try:
            # Convert query to hashtag (remove spaces, special chars)
            hashtag = query.replace(' ', '').replace('#', '')
            
            logger.info(f"Searching Mastodon hashtag: #{hashtag}")
            
            # Try to get hashtag timeline (doesn't require special permissions)
            try:
                statuses = self.client.timeline_hashtag(
                    hashtag,
                    limit=limit * 3  # Get more to filter
                )
            except:
                # Fallback: try public timeline and filter
                logger.info("Hashtag search failed, trying public timeline")
                statuses = self.client.timeline_public(limit=40)
            
            posts = []
            keywords = query.lower().split()
            
            for status in statuses:
                # Skip own posts if account_id provided
                if account_id and status['account']['id'] == account_id:
                    continue
                
                # Skip replies to avoid threading issues
                if status.get('in_reply_to_id'):
                    continue
                
                # Check if post content matches keywords
                content_lower = status.get('content', '').lower()
                if not any(keyword in content_lower for keyword in keywords):
                    # Also check hashtags
                    post_tags = [tag.get('name', '').lower() for tag in status.get('tags', [])]
                    if not any(keyword in tag for keyword in keywords for tag in post_tags):
                        continue
                
                posts.append({
                    'id': status['id'],
                    'content': status['content'],
                    'url': status['url'],
                    'created_at': status['created_at'].isoformat() if hasattr(status['created_at'], 'isoformat') else str(status['created_at']),
                    'account': {
                        'username': status['account']['username'],
                        'display_name': status['account']['display_name'],
                        'url': status['account']['url']
                    },
                    'favourites_count': status.get('favourites_count', 0),
                    'reblogs_count': status.get('reblogs_count', 0),
                    'replies_count': status.get('replies_count', 0)
                })
                
                if len(posts) >= limit:
                    break
            
            logger.info(f"Found {len(posts)} relevant posts")
            return posts
            
        except Exception as e:
            logger.error(f"Error searching Mastodon: {e}")
            return []
    
    def get_notifications(
        self,
        since_id: Optional[str] = None,
        limit: int = 20,
        types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch notifications (e.g. mentions) for the logged-in account.

        Args:
            since_id: Return only notifications after this ID (for polling).
            limit: Maximum number to return.
            types: Optional list of notification types (e.g. ['mention']).

        Returns:
            List of notification objects (id, type, created_at, status, account, ...).
        """
        try:
            kwargs: Dict[str, Any] = {"limit": limit}
            if since_id is not None:
                kwargs["since_id"] = since_id
            if types is not None:
                kwargs["types"] = types
            notifications = self.client.notifications(**kwargs)
            return list(notifications) if notifications else []
        except Exception as e:
            logger.error("Error fetching notifications: %s", e)
            return []

    def reply_to_status(
        self,
        status_id: str,
        reply_content: str,
        visibility: str = "public"
    ) -> Dict[str, Any]:
        """
        Reply to a specific status
        
        Args:
            status_id: ID of status to reply to
            reply_content: Reply content
            visibility: Visibility setting
            
        Returns:
            Posted reply information
        """
        try:
            logger.info(f"Replying to status {status_id}")
            
            status = self.client.status_post(
                status=reply_content,
                in_reply_to_id=status_id,
                visibility=visibility
            )
            
            logger.info(f"Successfully replied. Reply ID: {status['id']}")
            
            return {
                'id': status['id'],
                'url': status['url'],
                'created_at': status['created_at'].isoformat(),
                'in_reply_to_id': status_id
            }
            
        except Exception as e:
            logger.error(f"Error replying to status: {e}")
            raise
    
    def post_with_media(
        self,
        content: str,
        image_paths: List[str],
        visibility: str = "public",
        sensitive: bool = False,
        spoiler_text: Optional[str] = None,
        image_descriptions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Post content to Mastodon with images
        
        Args:
            content: Post content
            image_paths: List of paths to image files
            visibility: Visibility setting (public, unlisted, private, direct)
            sensitive: Mark as sensitive content
            spoiler_text: Content warning text
            image_descriptions: Optional list of alt text descriptions for images
            
        Returns:
            Posted status information
        """
        try:
            # Resolve relative paths to absolute so approval works from any cwd (e.g. telegram_bot_server)
            resolved_paths = []
            for raw_path in image_paths:
                p = Path(raw_path)
                if not p.is_absolute():
                    p = APP_ROOT / raw_path
                if not p.exists():
                    logger.warning("Image path does not exist, skipping: %s", p)
                    continue
                resolved_paths.append(str(p))

            logger.info(f"Posting to Mastodon with {len(resolved_paths)} images ({len(content)} chars)")
            if len(resolved_paths) < len(image_paths):
                logger.warning("Resolved %d/%d image paths (some missing)", len(resolved_paths), len(image_paths))

            # Upload media files first
            media_ids = []
            for i, image_path in enumerate(resolved_paths):
                try:
                    description = None
                    if image_descriptions and i < len(image_descriptions):
                        description = image_descriptions[i]

                    logger.info(f"Uploading media {i+1}/{len(resolved_paths)}: {image_path}")

                    media = self.client.media_post(
                        media_file=image_path,
                        description=description
                    )

                    media_ids.append(media['id'])
                    logger.info(f"Uploaded media ID: {media['id']}")

                except Exception as e:
                    logger.error("Error uploading media %s: %s", image_path, e, exc_info=True)
                    # WebP fallback: if instance rejects WebP, try converting to PNG and retry
                    png_path = None
                    if image_path.lower().endswith(".webp"):
                        try:
                            from PIL import Image
                            with Image.open(image_path) as img:
                                if img.mode in ("RGBA", "P"):
                                    img = img.convert("RGB")
                                png_path = tempfile.NamedTemporaryFile(
                                    delete=False, suffix=".png"
                                ).name
                                img.save(png_path, "PNG")
                            media = self.client.media_post(
                                media_file=png_path,
                                description=description if (image_descriptions and i < len(image_descriptions)) else None,
                            )
                            media_ids.append(media["id"])
                            logger.info("Uploaded media as PNG (WebP fallback): %s", media["id"])
                        except Exception as e2:
                            logger.warning("WebP to PNG fallback failed for %s: %s", image_path, e2)
                        finally:
                            if png_path and Path(png_path).exists():
                                try:
                                    os.unlink(png_path)
                                except OSError:
                                    pass
                    continue

            logger.info("Uploaded %d/%d images", len(media_ids), len(resolved_paths))
            if not media_ids:
                paths_log = resolved_paths if len(resolved_paths) <= 5 else resolved_paths[:5] + ["..."]
                logger.warning(
                    "No media uploaded successfully (tried %d path(s)): %s. Posting text only.",
                    len(resolved_paths), paths_log
                )
                return self.post(content, visibility, sensitive, spoiler_text)
            
            # Post status with media
            status = self.client.status_post(
                status=content,
                media_ids=media_ids,
                visibility=visibility,
                sensitive=sensitive,
                spoiler_text=spoiler_text
            )
            
            logger.info(f"Successfully posted with media. Status ID: {status['id']}")
            logger.info(f"URL: {status['url']}")
            
            return {
                'id': status['id'],
                'url': status['url'],
                'created_at': status['created_at'].isoformat(),
                'visibility': visibility,
                'media_count': len(media_ids),
                'favourites_count': status.get('favourites_count', 0),
                'reblogs_count': status.get('reblogs_count', 0)
            }
            
        except Exception as e:
            logger.error(f"Error posting with media to Mastodon: {e}")
            raise

