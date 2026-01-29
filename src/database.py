"""
Database models and connection management for TrustStackSocial
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

Base = declarative_base()


class Post(Base):
    """Social media post model"""
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    style = Column(String(50), nullable=False)
    length = Column(Integer, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    posted = Column(Boolean, default=False, nullable=False)
    posted_at = Column(DateTime, nullable=True)
    mastodon_url = Column(String(500), nullable=True)
    mastodon_id = Column(String(100), nullable=True)
    
    # Relationships
    replies = relationship("Reply", back_populates="post", cascade="all, delete-orphan")


class Article(Base):
    """Article model from RSS feeds"""
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=False, unique=True)
    summary = Column(Text, nullable=True)
    source = Column(String(200), nullable=False)
    published_date = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    matched_keywords = Column(JSON, nullable=True)  # List of matched keywords
    relevance_score = Column(Integer, default=0, nullable=False)
    
    # Relationships
    comments = relationship("Comment", back_populates="article", cascade="all, delete-orphan")


class Comment(Base):
    """Comment on article model"""
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    content = Column(Text, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    posted = Column(Boolean, default=False, nullable=False)
    posted_at = Column(DateTime, nullable=True)
    mastodon_url = Column(String(500), nullable=True)
    mastodon_id = Column(String(100), nullable=True)
    
    # Relationships
    article = relationship("Article", back_populates="comments")


class Reply(Base):
    """Reply to Mastodon post model"""
    __tablename__ = "replies"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)  # Can be null if replying to external post
    original_post_id = Column(String(100), nullable=True)  # Mastodon post ID being replied to
    original_post_url = Column(String(500), nullable=True)
    original_author = Column(String(200), nullable=True)
    content = Column(Text, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    posted = Column(Boolean, default=False, nullable=False)
    posted_at = Column(DateTime, nullable=True)
    mastodon_url = Column(String(500), nullable=True)
    mastodon_id = Column(String(100), nullable=True)
    should_reply = Column(Boolean, default=True, nullable=False)
    reason = Column(Text, nullable=True)
    
    # Relationships
    post = relationship("Post", back_populates="replies")


class WorkflowRun(Base):
    """Workflow execution log model"""
    __tablename__ = "workflow_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_type = Column(String(50), nullable=False)  # 'full', 'posts', 'articles', 'comments'
    status = Column(String(20), nullable=False)  # 'running', 'completed', 'failed'
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    posts_generated = Column(Integer, default=0, nullable=False)
    articles_fetched = Column(Integer, default=0, nullable=False)
    comments_generated = Column(Integer, default=0, nullable=False)
    workflow_metadata = Column(JSON, nullable=True)  # Additional workflow metadata


class PendingPost(Base):
    """Pending post awaiting approval"""
    __tablename__ = "pending_posts"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    style = Column(String(50), nullable=False)
    length = Column(Integer, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    image_paths = Column(JSON, nullable=True)  # List of logo/image paths
    comic_media_url = Column(Text, nullable=True)  # Replicate output URL for comic (fallback when local file missing at approval)
    news_context = Column(JSON, nullable=True)  # List of article IDs used
    news_quotes = Column(JSON, nullable=True)  # List of quotes from articles included in post
    status = Column(String(20), default="pending", nullable=False)  # pending, approved, rejected, expired, archived
    telegram_message_id = Column(String(100), nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Relationships
    approvals = relationship("PostApproval", back_populates="pending_post", cascade="all, delete-orphan")


class PostApproval(Base):
    """Post approval audit log"""
    __tablename__ = "post_approvals"
    
    id = Column(Integer, primary_key=True, index=True)
    pending_post_id = Column(Integer, ForeignKey("pending_posts.id"), nullable=False)
    action = Column(String(20), nullable=False)  # approve, reject
    telegram_user_id = Column(String(100), nullable=True)
    telegram_username = Column(String(200), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text, nullable=True)
    
    # Relationships
    pending_post = relationship("PendingPost", back_populates="approvals")


# Database connection management
def get_database_path() -> str:
    """Get the database file path"""
    # Check for environment variable first
    db_path = os.getenv("DATABASE_PATH")
    if db_path:
        return db_path
    
    # Default to data directory in project root
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    
    return str(data_dir / "truststacksocial.db")


def get_engine():
    """Get SQLAlchemy engine"""
    database_path = get_database_path()
    database_url = f"sqlite:///{database_path}"
    
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},  # Needed for SQLite
        echo=False  # Set to True for SQL query logging
    )
    
    return engine


def get_session() -> Session:
    """Get database session"""
    engine = get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def init_db():
    """Initialize database tables"""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return engine


def get_db():
    """Dependency for FastAPI to get database session"""
    db = get_session()
    try:
        yield db
    finally:
        db.close()
