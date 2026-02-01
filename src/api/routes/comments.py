"""
Comment generation endpoints
"""
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..models import (
    CommentResponse, CommentListResponse, CommentGenerateRequest
)
from ..dependencies import get_database, get_app_config
from ...database import Comment, Article
from ...config import Config
from ...notion_client import NotionClient
from ...openrouter_client import OpenrouterClient
from ...comment_generator import CommentGenerator

router = APIRouter(prefix="/comments", tags=["comments"])


@router.post("/generate", response_model=CommentListResponse, status_code=status.HTTP_201_CREATED)
def generate_comments(
    request: CommentGenerateRequest,
    db: Session = Depends(get_database),
    config: Config = Depends(get_app_config)
):
    """Generate comments for articles"""
    try:
        # Get articles
        if request.article_ids:
            articles_query = db.query(Article).filter(Article.id.in_(request.article_ids))
        else:
            # Get recent articles
            articles_query = db.query(Article).order_by(Article.fetched_at.desc()).limit(10)
        
        db_articles = articles_query.all()
        
        if not db_articles:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No articles found"
            )
        
        # Convert to dict format for CommentGenerator
        articles_data = []
        for db_article in db_articles:
            articles_data.append({
                'id': db_article.id,
                'title': db_article.title,
                'url': db_article.url,
                'summary': db_article.summary,
                'source': db_article.source
            })
        
        notion_client = NotionClient(
            config.notion_api_key,
            config.notion_page_id or "",
            database_id=getattr(config, 'notion_database_id', None),
        )
        openrouter_client = OpenrouterClient(config.openrouter_api_key, config.openrouter_model)
        
        # Initialize comment generator
        max_length = config.comment_settings.get('max_length', 300)
        comment_generator = CommentGenerator(openrouter_client, notion_client, max_length)
        
        # Generate comments
        comments_data = comment_generator.generate_comments(
            articles=articles_data,
            temperature=request.temperature
        )
        
        # Save to database
        db_comments = []
        for item in comments_data:
            if not item.get('comment'):
                continue
            
            # Find article
            article_id = item.get('id')
            article = db.query(Article).filter(Article.id == article_id).first()
            
            if not article:
                continue
            
            # Create comment
            db_comment = Comment(
                article_id=article.id,
                content=item['comment'],
                generated_at=datetime.fromisoformat(item.get('comment_generated_at', datetime.utcnow().isoformat())),
                posted=False
            )
            db.add(db_comment)
            db_comments.append(db_comment)
        
        db.commit()
        
        # Refresh to get IDs
        for db_comment in db_comments:
            db.refresh(db_comment)
        
        return CommentListResponse(
            comments=[CommentResponse.model_validate(c) for c in db_comments],
            total=len(db_comments)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating comments: {str(e)}"
        )


@router.get("", response_model=CommentListResponse)
def list_comments(
    skip: int = 0,
    limit: int = 50,
    posted: Optional[bool] = None,
    db: Session = Depends(get_database)
):
    """List comments with pagination"""
    query = db.query(Comment)
    
    if posted is not None:
        query = query.filter(Comment.posted == posted)
    
    total = query.count()
    comments = query.order_by(Comment.generated_at.desc()).offset(skip).limit(limit).all()
    
    return CommentListResponse(
        comments=[CommentResponse.from_orm(c) for c in comments],
        total=total
    )


@router.get("/{comment_id}", response_model=CommentResponse)
def get_comment(comment_id: int, db: Session = Depends(get_database)):
    """Get comment by ID"""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment {comment_id} not found"
        )
    
    return CommentResponse.model_validate(comment)
