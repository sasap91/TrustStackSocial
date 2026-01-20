"""
Mastodon API client for posting social media content
"""
import logging
from typing import Dict, Any, Optional
from mastodon import Mastodon

logger = logging.getLogger(__name__)


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
        
        # Verify credentials
        try:
            account = self.client.account_verify_credentials()
            logger.info(f"Logged in as: @{account['username']}")
        except Exception as e:
            logger.error(f"Failed to verify Mastodon credentials: {e}")
            raise
    
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

