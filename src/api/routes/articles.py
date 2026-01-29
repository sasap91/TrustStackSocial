"""
Article fetching endpoints
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..models import (
    ArticleResponse, ArticleListResponse, ArticleFetchRequest
)
from ..dependencies import get_database, get_app_config
from ...database import Article
from ...config import Config
from ...article_fetcher import ArticleFetcher

router = APIRouter(prefix="/articles", tags=["articles"])


@router.post("/fetch", response_model=ArticleListResponse, status_code=status.HTTP_201_CREATED)
def fetch_articles(
    request: ArticleFetchRequest,
    db: Session = Depends(get_database),
    config: Config = Depends(get_app_config)
):
    """Fetch articles from RSS feeds"""
    try:
        # Initialize article fetcher
        article_fetcher = ArticleFetcher(
            rss_feeds=config.rss_feeds,
            keywords=config.article_keywords,
            max_articles_per_feed=config.article_settings.get('max_articles_per_feed', 20)
        )
        
        # Fetch articles
        articles_data = article_fetcher.get_top_articles(
            count=request.count,
            min_age_hours=request.min_age_hours,
            max_age_days=request.max_age_days
        )
        
        # Save to database (avoid duplicates)
        db_articles = []
        for article_data in articles_data:
            # Check if article already exists
            existing = db.query(Article).filter(Article.url == article_data['url']).first()
            
            if existing:
                db_articles.append(existing)
                continue
            
            # Create new article
            db_article = Article(
                title=article_data['title'],
                url=article_data['url'],
                summary=article_data.get('summary'),
                source=article_data.get('source', 'Unknown'),
                published_date=article_data.get('published_date'),
                matched_keywords=article_data.get('matched_keywords', []),
                relevance_score=article_data.get('relevance_score', 0)
            )
            db.add(db_article)
            db_articles.append(db_article)
        
        db.commit()
        
        # Refresh to get IDs
        for db_article in db_articles:
            db.refresh(db_article)
        
        return ArticleListResponse(
            articles=[ArticleResponse.model_validate(a) for a in db_articles],
            total=len(db_articles)
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching articles: {str(e)}"
        )


@router.get("", response_model=ArticleListResponse)
def list_articles(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_database)
):
    """List articles with pagination"""
    total = db.query(Article).count()
    articles = db.query(Article).order_by(Article.fetched_at.desc()).offset(skip).limit(limit).all()
    
    return ArticleListResponse(
        articles=[ArticleResponse.model_validate(a) for a in articles],
        total=total
    )


@router.get("/{article_id}", response_model=ArticleResponse)
def get_article(article_id: int, db: Session = Depends(get_database)):
    """Get article by ID"""
    article = db.query(Article).filter(Article.id == article_id).first()
    
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article {article_id} not found"
        )
    
    return ArticleResponse.model_validate(article)
