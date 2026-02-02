"""
Migration script to migrate JSON files to SQLite database
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from .database import init_db, get_session, Post, Article, Comment, Reply, WorkflowRun

logger = logging.getLogger(__name__)


def parse_datetime(date_str: str) -> datetime:
    """Parse ISO format datetime string"""
    try:
        if isinstance(date_str, str):
            # Handle ISO format with or without microseconds
            if 'T' in date_str:
                if '.' in date_str:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00').replace('T', ' '))
            return datetime.fromisoformat(date_str)
    except Exception as e:
        logger.warning(f"Failed to parse datetime {date_str}: {e}")
    return datetime.utcnow()


def migrate_posts(output_dir: Path, db_session) -> int:
    """Migrate posts.json to database"""
    posts_file = output_dir / "posts.json"
    
    if not posts_file.exists():
        logger.info("posts.json not found, skipping")
        return 0
    
    try:
        with open(posts_file, 'r') as f:
            posts_data = json.load(f)
        
        if not isinstance(posts_data, list):
            logger.warning("posts.json is not a list, skipping")
            return 0
        
        migrated_count = 0
        
        for post_data in posts_data:
            # Check if post already exists (by content hash or id)
            existing = db_session.query(Post).filter(
                Post.content == post_data.get('content', '')
            ).first()
            
            if existing:
                logger.debug(f"Post already exists, skipping: {post_data.get('id', 'unknown')}")
                continue
            
            # Create post
            post = Post(
                content=post_data.get('content', ''),
                style=post_data.get('style', 'professional'),
                length=post_data.get('length', 0),
                generated_at=parse_datetime(post_data.get('generated_at', datetime.utcnow().isoformat())),
                posted=post_data.get('posted', False),
                mastodon_url=post_data.get('mastodon_url'),
                mastodon_id=post_data.get('mastodon_id')
            )
            
            if post_data.get('posted_at'):
                post.posted_at = parse_datetime(post_data['posted_at'])
            
            db_session.add(post)
            migrated_count += 1
        
        db_session.commit()
        logger.info(f"Migrated {migrated_count} posts")
        return migrated_count
        
    except Exception as e:
        logger.error(f"Error migrating posts: {e}")
        db_session.rollback()
        return 0


def migrate_articles(output_dir: Path, db_session) -> int:
    """Migrate articles.json to database"""
    articles_file = output_dir / "articles.json"
    
    if not articles_file.exists():
        logger.info("articles.json not found, skipping")
        return 0
    
    try:
        with open(articles_file, 'r') as f:
            articles_data = json.load(f)
        
        if not isinstance(articles_data, list):
            logger.warning("articles.json is not a list, skipping")
            return 0
        
        migrated_count = 0
        
        for article_data in articles_data:
            # Check if article already exists (by URL)
            url = article_data.get('url', '')
            if not url:
                continue
            
            existing = db_session.query(Article).filter(Article.url == url).first()
            
            if existing:
                logger.debug(f"Article already exists, skipping: {article_data.get('title', 'unknown')}")
                continue
            
            # Create article
            article = Article(
                title=article_data.get('title', ''),
                url=url,
                summary=article_data.get('summary'),
                source=article_data.get('source', 'Unknown'),
                published_date=parse_datetime(article_data['published_date']) if article_data.get('published_date') else None,
                fetched_at=parse_datetime(article_data.get('fetched_at', datetime.utcnow().isoformat())),
                matched_keywords=article_data.get('matched_keywords', []),
                relevance_score=article_data.get('relevance_score', 0)
            )
            
            db_session.add(article)
            migrated_count += 1
        
        db_session.commit()
        logger.info(f"Migrated {migrated_count} articles")
        return migrated_count
        
    except Exception as e:
        logger.error(f"Error migrating articles: {e}")
        db_session.rollback()
        return 0


def migrate_comments(output_dir: Path, db_session) -> int:
    """Migrate comments.json to database"""
    comments_file = output_dir / "comments.json"
    
    if not comments_file.exists():
        logger.info("comments.json not found, skipping")
        return 0
    
    try:
        with open(comments_file, 'r') as f:
            comments_data = json.load(f)
        
        if not isinstance(comments_data, list):
            logger.warning("comments.json is not a list, skipping")
            return 0
        
        migrated_count = 0
        
        for item_data in comments_data:
            # Find or create article
            article_url = item_data.get('url', '')
            if not article_url:
                continue
            
            article = db_session.query(Article).filter(Article.url == article_url).first()
            
            if not article:
                # Create article if it doesn't exist
                article = Article(
                    title=item_data.get('title', ''),
                    url=article_url,
                    summary=item_data.get('summary'),
                    source=item_data.get('source', 'Unknown'),
                    published_date=parse_datetime(item_data['published_date']) if item_data.get('published_date') else None,
                    fetched_at=datetime.utcnow(),
                    matched_keywords=item_data.get('matched_keywords', []),
                    relevance_score=item_data.get('relevance_score', 0)
                )
                db_session.add(article)
                db_session.flush()  # Get article ID
            
            # Check if comment already exists
            comment_content = item_data.get('comment', '')
            if not comment_content:
                continue
            
            existing = db_session.query(Comment).filter(
                Comment.article_id == article.id,
                Comment.content == comment_content
            ).first()
            
            if existing:
                logger.debug(f"Comment already exists, skipping")
                continue
            
            # Create comment
            comment = Comment(
                article_id=article.id,
                content=comment_content,
                generated_at=parse_datetime(item_data.get('comment_generated_at', datetime.utcnow().isoformat())),
                posted=item_data.get('posted', False),
                mastodon_url=item_data.get('mastodon_url'),
                mastodon_id=item_data.get('mastodon_id')
            )
            
            if item_data.get('posted_at'):
                comment.posted_at = parse_datetime(item_data['posted_at'])
            
            db_session.add(comment)
            migrated_count += 1
        
        db_session.commit()
        logger.info(f"Migrated {migrated_count} comments")
        return migrated_count
        
    except Exception as e:
        logger.error(f"Error migrating comments: {e}")
        db_session.rollback()
        return 0


def migrate_replies(output_dir: Path, db_session) -> int:
    """Migrate replies.json to database"""
    replies_file = output_dir / "replies.json"
    
    if not replies_file.exists():
        logger.info("replies.json not found, skipping")
        return 0
    
    try:
        with open(replies_file, 'r') as f:
            replies_data = json.load(f)
        
        if not isinstance(replies_data, list):
            logger.warning("replies.json is not a list, skipping")
            return 0
        
        migrated_count = 0
        
        for reply_data in replies_data:
            # Check if reply already exists
            reply_content = reply_data.get('reply', '')
            if not reply_content:
                continue
            
            original_post_id = reply_data.get('id')  # Mastodon post ID
            
            existing = db_session.query(Reply).filter(
                Reply.original_post_id == str(original_post_id),
                Reply.content == reply_content
            ).first()
            
            if existing:
                logger.debug(f"Reply already exists, skipping")
                continue
            
            # Create reply
            reply = Reply(
                original_post_id=str(original_post_id) if original_post_id else None,
                original_post_url=reply_data.get('url'),
                original_author=reply_data.get('account', {}).get('username') if isinstance(reply_data.get('account'), dict) else None,
                content=reply_content,
                generated_at=parse_datetime(reply_data.get('generated_at', datetime.utcnow().isoformat())),
                posted=reply_data.get('posted', False),
                mastodon_url=reply_data.get('mastodon_url'),
                mastodon_id=reply_data.get('mastodon_id'),
                should_reply=reply_data.get('should_reply', True),
                reason=reply_data.get('reason')
            )
            
            if reply_data.get('posted_at'):
                reply.posted_at = parse_datetime(reply_data['posted_at'])
            
            db_session.add(reply)
            migrated_count += 1
        
        db_session.commit()
        logger.info(f"Migrated {migrated_count} replies")
        return migrated_count
        
    except Exception as e:
        logger.error(f"Error migrating replies: {e}")
        db_session.rollback()
        return 0


def migrate_all(output_dir: str = "output", dry_run: bool = False) -> Dict[str, int]:
    """
    Migrate all JSON files to database
    
    Args:
        output_dir: Directory containing JSON files
        dry_run: If True, don't actually migrate, just report
        
    Returns:
        Dictionary with migration counts
    """
    output_path = Path(output_dir)
    
    if not output_path.exists():
        logger.warning(f"Output directory not found: {output_dir}")
        return {}
    
    logger.info(f"Starting migration from {output_dir} to database")
    
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    
    # Initialize database
    init_db()
    
    if dry_run:
        return {
            'posts': 0,
            'articles': 0,
            'comments': 0,
            'replies': 0
        }
    
    db_session = get_session()
    
    try:
        results = {
            'posts': migrate_posts(output_path, db_session),
            'articles': migrate_articles(output_path, db_session),
            'comments': migrate_comments(output_path, db_session),
            'replies': migrate_replies(output_path, db_session)
        }
        
        total = sum(results.values())
        logger.info(f"Migration complete! Migrated {total} total items")
        
        return results
        
    finally:
        db_session.close()


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "output"
    dry_run = "--dry-run" in sys.argv
    
    results = migrate_all(output_dir, dry_run)
    
    print("\nMigration Results:")
    for key, count in results.items():
        print(f"  {key}: {count}")
