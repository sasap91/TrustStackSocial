"""
Post generation and management endpoints
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ..models import (
    PostCreate, PostResponse, PostListResponse, PostPublishRequest
)
from ..dependencies import get_database, get_app_config
from ...database import Post, PendingPost, get_session, init_db
from ...config import Config
from ...notion_client import NotionClient
from ...openrouter_client import OpenrouterClient
from ...post_generator import PostGenerator
from ...mastodon_client import MastodonClient
from ...article_fetcher import ArticleFetcher
from ...enhanced_post_generator import EnhancedPostGenerator
from ...manual_post_generator import ManualPostGenerator
from ...telegram_bot import TelegramBot
from ...approval_workflow import ApprovalWorkflow
from ...image_handler import LogoHandler

# Optional import for image generation
try:
    from ...replicate_image_generator import ReplicateImageGenerator
    REPLICATE_AVAILABLE = True
except ImportError:
    REPLICATE_AVAILABLE = False
    ReplicateImageGenerator = None

# Optional RAG retriever
try:
    from ...rag import RAGRetriever
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    RAGRetriever = None

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("/generate", response_model=PostListResponse, status_code=status.HTTP_201_CREATED)
def generate_posts(
    request: PostCreate,
    db: Session = Depends(get_database),
    config: Config = Depends(get_app_config)
):
    """Generate social media posts (with RAG when indexed)"""
    try:
        notion_client = NotionClient(
            config.notion_api_key,
            config.notion_page_id or "",
            database_id=getattr(config, 'notion_database_id', None),
        )
        openrouter_client = OpenrouterClient(config.openrouter_api_key, config.openrouter_model)
        max_length = config.post_settings.get('max_length', 500)
        rag_retriever = RAGRetriever() if (RAG_AVAILABLE and RAGRetriever) else None
        post_generator = PostGenerator(
            notion_client, openrouter_client, max_length, rag_retriever=rag_retriever
        )
        
        # Generate posts
        posts_data = post_generator.generate_posts(
            count=request.count,
            temperature=request.temperature
        )
        
        # Save to database
        db_posts = []
        for post_data in posts_data:
            db_post = Post(
                content=post_data['content'],
                style=post_data['style'],
                length=post_data['length'],
                generated_at=datetime.fromisoformat(post_data['generated_at']),
                posted=False
            )
            db.add(db_post)
            db_posts.append(db_post)
        
        db.commit()
        
        # Refresh to get IDs
        for db_post in db_posts:
            db.refresh(db_post)
        
        return PostListResponse(
            posts=[PostResponse.model_validate(p) for p in db_posts],
            total=len(db_posts)
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating posts: {str(e)}"
        )


@router.get("", response_model=PostListResponse)
def list_posts(
    skip: int = 0,
    limit: int = 50,
    posted: Optional[bool] = None,
    db: Session = Depends(get_database)
):
    """List posts with pagination"""
    query = db.query(Post)
    
    if posted is not None:
        query = query.filter(Post.posted == posted)
    
    total = query.count()
    posts = query.order_by(Post.generated_at.desc()).offset(skip).limit(limit).all()
    
    return PostListResponse(
        posts=[PostResponse.model_validate(p) for p in posts],
        total=total
    )


@router.get("/{post_id}", response_model=PostResponse)
def get_post(post_id: int, db: Session = Depends(get_database)):
    """Get post by ID"""
    post = db.query(Post).filter(Post.id == post_id).first()
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post {post_id} not found"
        )
    
    return PostResponse.model_validate(post)


@router.post("/{post_id}/publish", response_model=PostResponse)
def publish_post(
    post_id: int,
    request: PostPublishRequest,
    db: Session = Depends(get_database),
    config: Config = Depends(get_app_config)
):
    """Publish post to Mastodon"""
    post = db.query(Post).filter(Post.id == post_id).first()
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post {post_id} not found"
        )
    
    if request.preview:
        # Return preview without posting
        return PostResponse.model_validate(post)
    
    try:
        # Initialize Mastodon client
        mastodon_client = MastodonClient(
            config.mastodon_access_token,
            config.mastodon_api_base_url
        )
        
        # Post to Mastodon
        result = mastodon_client.post(post.content)
        
        # Update post
        post.posted = True
        post.posted_at = datetime.utcnow()
        post.mastodon_url = result.get('url')
        post.mastodon_id = str(result.get('id', ''))
        
        db.commit()
        db.refresh(post)
        
        return PostResponse.model_validate(post)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error publishing post: {str(e)}"
        )


@router.post("/generate-pending", status_code=status.HTTP_201_CREATED)
def generate_pending_post(
    style: str = "professional",
    temperature: float = 0.7,
    max_articles: int = 3,
    db: Session = Depends(get_database),
    config: Config = Depends(get_app_config)
):
    """Generate a post with news and queue for Telegram approval"""
    # Validate Telegram configuration
    if not config.telegram_bot_token or not config.telegram_chat_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram bot token and chat ID must be configured"
        )
    
    try:
        # Initialize database
        init_db()
        
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
        rag_retriever = RAGRetriever() if (RAG_AVAILABLE and RAGRetriever) else None
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
        
        # Initialize Telegram bot
        telegram_bot = TelegramBot(
            bot_token=config.telegram_bot_token,
            approval_chat_id=config.telegram_chat_id
        )
        
        # Initialize approval workflow
        telegram_settings = config.telegram_settings
        approval_workflow = ApprovalWorkflow(
            telegram_bot=telegram_bot,
            mastodon_client=mastodon_client,
            logo_handler=logo_handler,
            approval_timeout_hours=telegram_settings.get('approval_timeout_hours', 24)
        )
        
        # Initialize image generator if available and enabled
        image_generator = None
        if REPLICATE_AVAILABLE and config.replicate_api_token:
            image_gen_settings = config.image_generation_settings
            if image_gen_settings.get('enabled', True):
                try:
                    image_generator = ReplicateImageGenerator(
                        replicate_api_token=config.replicate_api_token,
                        openrouter_client=openrouter_client,
                        model=image_gen_settings.get('replicate_model', 'sundai-club/truststacksocial:b897202db67596183259c5dfaa424ddeb898cc5923934fe8afdd8e096c721517'),
                        trigger_word=image_gen_settings.get('trigger_word', 'truststack'),
                        model_type=image_gen_settings.get('model_type', 'schnell'),
                        num_inference_steps=image_gen_settings.get('num_inference_steps', 4),
                        guidance_scale=image_gen_settings.get('guidance_scale', 7.5),
                        style_suffix=image_gen_settings.get('style_suffix', 'cartoonish style, pastel colors'),
                        image_directory=image_gen_settings.get('image_directory', 'assets/generated_images')
                    )
                except Exception as e:
                    # Log but don't fail - continue without image generation
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to initialize ReplicateImageGenerator: {e}")
                    image_generator = None
        
        # Initialize manual post generator
        manual_generator = ManualPostGenerator(
            enhanced_generator, approval_workflow, logo_handler, image_generator
        )
        
        # Generate and queue post
        result = manual_generator.generate_and_queue_post(
            style=style,
            temperature=temperature,
            max_articles=max_articles,
            db_session=db
        )
        
        if result.get('success'):
            return {
                'success': True,
                'pending_post_id': result['pending_post_id'],
                'message': 'Post generated and queued for approval'
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get('error', 'Failed to generate post')
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating pending post: {str(e)}"
        )


@router.get("/pending")
def list_pending_posts(
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_database)
):
    """List pending posts awaiting approval"""
    query = db.query(PendingPost)
    
    if status_filter:
        query = query.filter(PendingPost.status == status_filter)
    else:
        query = query.filter(PendingPost.status == "pending")
    
    total = query.count()
    posts = query.order_by(PendingPost.generated_at.desc()).offset(skip).limit(limit).all()
    
    return {
        'pending_posts': [{
            'id': p.id,
            'content': p.content,
            'style': p.style,
            'status': p.status,
            'generated_at': p.generated_at.isoformat(),
            'articles_count': len(p.news_context or []),
            'quotes_count': len(p.news_quotes or []),
            'has_images': bool(p.image_paths)
        } for p in posts],
        'total': total
    }


@router.post("/{post_id}/approve")
def approve_pending_post(
    post_id: int,
    db: Session = Depends(get_database),
    config: Config = Depends(get_app_config)
):
    """Approve a pending post (API fallback)"""
    if not config.telegram_bot_token or not config.telegram_chat_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram bot not configured"
        )
    
    try:
        mastodon_client = MastodonClient(config.mastodon_access_token, config.mastodon_api_base_url)
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
        
        success = approval_workflow.process_approval(post_id, db_session=db)
        
        if success:
            return {'success': True, 'message': f'Post {post_id} approved and posted'}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Failed to approve post {post_id}'
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error approving post: {str(e)}"
        )


@router.post("/{post_id}/reject")
def reject_pending_post(
    post_id: int,
    reason: Optional[str] = Query(None),
    db: Session = Depends(get_database),
    config: Config = Depends(get_app_config)
):
    """Reject a pending post (API fallback)"""
    if not config.telegram_bot_token or not config.telegram_chat_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram bot not configured"
        )
    
    try:
        mastodon_client = MastodonClient(config.mastodon_access_token, config.mastodon_api_base_url)
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
            post_id,
            rejection_reason=reason,
            db_session=db
        )
        
        if success:
            return {'success': True, 'message': f'Post {post_id} rejected and archived'}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Failed to reject post {post_id}'
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rejecting post: {str(e)}"
        )
