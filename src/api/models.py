"""
Pydantic models for request/response validation
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# Post models
class PostCreate(BaseModel):
    """Request model for generating posts"""
    count: int = Field(default=5, ge=1, le=20, description="Number of posts to generate")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")


class PostResponse(BaseModel):
    """Response model for post"""
    id: int
    content: str
    style: str
    length: int
    generated_at: datetime
    posted: bool
    posted_at: Optional[datetime] = None
    mastodon_url: Optional[str] = None
    
    class Config:
        from_attributes = True
        orm_mode = True


class PostListResponse(BaseModel):
    """Response model for post list"""
    posts: List[PostResponse]
    total: int


class PostPublishRequest(BaseModel):
    """Request model for publishing post"""
    preview: bool = Field(default=False, description="Preview without posting")


# Article models
class ArticleResponse(BaseModel):
    """Response model for article"""
    id: int
    title: str
    url: str
    summary: Optional[str] = None
    source: str
    published_date: Optional[datetime] = None
    fetched_at: datetime
    matched_keywords: List[str] = []
    relevance_score: int
    
    class Config:
        from_attributes = True
        orm_mode = True


class ArticleListResponse(BaseModel):
    """Response model for article list"""
    articles: List[ArticleResponse]
    total: int


class ArticleFetchRequest(BaseModel):
    """Request model for fetching articles"""
    count: int = Field(default=10, ge=1, le=50, description="Number of articles to fetch")
    min_age_hours: int = Field(default=1, ge=0, description="Minimum article age in hours")
    max_age_days: int = Field(default=7, ge=1, le=30, description="Maximum article age in days")


# Comment models
class CommentResponse(BaseModel):
    """Response model for comment"""
    id: int
    article_id: int
    content: str
    generated_at: datetime
    posted: bool
    posted_at: Optional[datetime] = None
    mastodon_url: Optional[str] = None
    
    class Config:
        from_attributes = True
        orm_mode = True


class CommentGenerateRequest(BaseModel):
    """Request model for generating comments"""
    article_ids: Optional[List[int]] = Field(default=None, description="Specific article IDs, or None for all")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class CommentListResponse(BaseModel):
    """Response model for comment list"""
    comments: List[CommentResponse]
    total: int


# Workflow models
class WorkflowRunRequest(BaseModel):
    """Request model for running workflow"""
    post_count: int = Field(default=3, ge=1, le=20)
    article_count: int = Field(default=5, ge=1, le=50)
    post_to_mastodon: bool = Field(default=False, description="Actually post to Mastodon")


class WorkflowRunResponse(BaseModel):
    """Response model for workflow run"""
    id: int
    workflow_type: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    posts_generated: int = 0
    articles_fetched: int = 0
    comments_generated: int = 0
    
    class Config:
        from_attributes = True
        orm_mode = True


# Health check models
class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    database: str
    timestamp: datetime
