"""
Manual post generator for creating posts with news and sending for approval
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from .enhanced_post_generator import EnhancedPostGenerator
from .approval_workflow import ApprovalWorkflow
from .image_handler import LogoHandler
from .database import get_session, Article

logger = logging.getLogger(__name__)

# Project root for resolving relative image paths (approval may run from another cwd)
APP_ROOT = Path(__file__).resolve().parent.parent

# Optional import for image generation
try:
    from .replicate_image_generator import ReplicateImageGenerator
    REPLICATE_AVAILABLE = True
except ImportError:
    REPLICATE_AVAILABLE = False
    ReplicateImageGenerator = None


class ManualPostGenerator:
    """Generate and queue posts for approval"""
    
    def __init__(
        self,
        enhanced_generator: EnhancedPostGenerator,
        approval_workflow: ApprovalWorkflow,
        logo_handler: LogoHandler,
        image_generator: Optional[Any] = None
    ):
        """
        Initialize manual post generator
        
        Args:
            enhanced_generator: Enhanced post generator instance
            approval_workflow: Approval workflow instance
            logo_handler: Logo handler instance
            image_generator: Optional ReplicateImageGenerator instance
        """
        self.enhanced_generator = enhanced_generator
        self.approval_workflow = approval_workflow
        self.logo_handler = logo_handler
        self.image_generator = image_generator
        logger.info("Initialized ManualPostGenerator")
    
    def generate_and_queue_post(
        self,
        style: str = "professional",
        temperature: float = 0.7,
        max_articles: int = 3,
        article_ids: Optional[list] = None,
        db_session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Generate post with news and queue for approval
        
        Args:
            style: Post style
            temperature: Sampling temperature
            max_articles: Maximum articles to use
            article_ids: Optional specific article IDs
            db_session: Database session
            
        Returns:
            Dictionary with result information
        """
        if db_session is None:
            db_session = get_session()
            close_session = True
        else:
            close_session = False
        
        try:
            logger.info(f"Generating post with news (style: {style})")
            
            # Generate post with news
            post_data = self.enhanced_generator.generate_post_with_news(
                article_ids=article_ids,
                max_articles=max_articles,
                style=style,
                temperature=temperature,
                db_session=db_session
            )
            
            # Select logo for post
            logo_path = self.logo_handler.select_logo_for_post(style=style)
            image_paths = [logo_path] if logo_path else []
            
            # Get article details for Telegram preview and image generation
            articles = []
            article_details = post_data.get('article_details', [])
            selected_articles = post_data.get('articles_used', [])
            if selected_articles:
                db_articles = db_session.query(Article).filter(
                    Article.id.in_(selected_articles)
                ).all()
                articles = [{
                    'id': a.id,
                    'title': a.title,
                    'url': a.url,
                    'source': a.source,
                    'summary': a.summary
                } for a in db_articles]
                # Use article_details from post_data when available (has summary)
                if article_details:
                    articles = article_details
            elif article_details:
                # No ids yet (e.g. from fetcher); use selected article_details so count and payload are correct
                articles = article_details
            
            # Generate comic image if image generator is available and enabled
            comic_image_path = None
            comic_media_url = None
            if self.image_generator:
                try:
                    logger.info("Generating comic image for post")
                    comic_image_path, comic_media_url = self.image_generator.generate_and_download_image(
                        post_content=post_data['content'],
                        articles=articles,
                        quotes=post_data.get('quotes_used', []),
                        pending_post_id=None  # Will be set after pending_post is created
                    )
                    
                    if comic_image_path:
                        # Add comic image to image_paths (before logo if logo exists)
                        image_paths.insert(0, comic_image_path)
                        logger.info(f"Generated comic image: {comic_image_path}")
                    else:
                        logger.warning("Comic image generation failed, continuing with logo only")
                except Exception as e:
                    logger.error(f"Error generating comic image: {e}", exc_info=True)
                    # Continue with logo only if image generation fails

            # Resolve to absolute, then store relative to project root so approval (any process/machine with same repo) can resolve
            image_paths_abs = []
            for p in image_paths:
                pt = Path(p)
                if not pt.is_absolute():
                    pt = APP_ROOT / p
                image_paths_abs.append(str(pt.resolve()))
            image_paths_for_db = []
            for p in image_paths_abs:
                pt = Path(p).resolve()
                try:
                    rel = pt.relative_to(APP_ROOT)
                    image_paths_for_db.append(str(rel))
                except ValueError:
                    image_paths_for_db.append(p)

            logger.info("Storing image_paths for pending post: %s", image_paths_for_db)
            # Create pending post
            pending_post = self.approval_workflow.create_pending_post(
                content=post_data['content'],
                style=post_data['style'],
                image_paths=image_paths_for_db,
                article_ids=post_data.get('articles_used', []),
                quotes=post_data.get('quotes_used', []),
                comic_media_url=comic_media_url,
                db_session=db_session
            )
            
            # If we generated a comic image but didn't have pending_post_id, update filename
            # (This is optional - the timestamp-based filename is fine)
            if comic_image_path and self.image_generator:
                try:
                    # Rename file to include pending_post_id if desired
                    # For now, we'll keep the timestamp-based name
                    pass
                except Exception as e:
                    logger.warning(f"Could not rename comic image: {e}")
            
            # Send for approval
            success = self.approval_workflow.send_for_approval(
                pending_post=pending_post,
                articles=articles,
                db_session=db_session
            )
            
            if success:
                logger.info(f"Successfully generated and queued post {pending_post.id} for approval")
                return {
                    'success': True,
                    'pending_post_id': pending_post.id,
                    'content': post_data['content'],
                    'style': post_data['style'],
                    'articles_used': len(post_data.get('articles_used', [])),
                    'quotes_used': len(post_data.get('quotes_used', [])),
                    'articles': articles,
                    'has_logo': bool(logo_path),
                    'has_comic_image': bool(comic_image_path)
                }
            else:
                logger.error(f"Failed to send post {pending_post.id} for approval")
                return {
                    'success': False,
                    'pending_post_id': pending_post.id,
                    'error': 'Failed to send to Telegram'
                }
                
        except Exception as e:
            logger.error(f"Error generating and queuing post: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            if close_session:
                db_session.close()
