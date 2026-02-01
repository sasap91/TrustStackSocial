"""
Workflow execution endpoints
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from ..models import WorkflowRunRequest, WorkflowRunResponse
from ..dependencies import get_database, get_app_config
from ...database import WorkflowRun
from ...config import Config

router = APIRouter(prefix="/workflows", tags=["workflows"])


def run_full_workflow(
    workflow_run_id: int,
    post_count: int,
    article_count: int,
    post_to_mastodon: bool,
    config: Config
):
    """Background task to run full workflow"""
    from ..dependencies import get_database
    db = next(get_database())
    
    try:
        workflow_run = db.query(WorkflowRun).filter(WorkflowRun.id == workflow_run_id).first()
        if not workflow_run:
            return
        
        workflow_run.status = "running"
        db.commit()
        
        # Import here to avoid circular imports
        from ...notion_client import NotionClient
        from ...openrouter_client import OpenrouterClient
        from ...post_generator import PostGenerator
        from ...article_fetcher import ArticleFetcher
        from ...comment_generator import CommentGenerator
        from ...mastodon_client import MastodonClient
        from ...database import Post, Article, Comment
        
        notion_client = NotionClient(
            config.notion_api_key,
            config.notion_page_id or "",
            database_id=getattr(config, 'notion_database_id', None),
        )
        openrouter_client = OpenrouterClient(config.openrouter_api_key, config.openrouter_model)
        mastodon_client = MastodonClient(config.mastodon_access_token, config.mastodon_api_base_url)
        max_length = config.post_settings.get('max_length', 500)
        try:
            from ...rag import RAGRetriever
            rag_retriever = RAGRetriever()
        except ImportError:
            rag_retriever = None
        post_generator = PostGenerator(
            notion_client, openrouter_client, max_length, rag_retriever=rag_retriever
        )
        posts_data = post_generator.generate_posts(count=post_count)
        
        posts_generated = 0
        for post_data in posts_data:
            db_post = Post(
                content=post_data['content'],
                style=post_data['style'],
                length=post_data['length'],
                generated_at=datetime.fromisoformat(post_data['generated_at']),
                posted=False
            )
            db.add(db_post)
            posts_generated += 1
        
        db.flush()
        
        # Step 2: Post first post to Mastodon if enabled
        if post_to_mastodon and posts_data:
            try:
                first_post = posts_data[0]
                result = mastodon_client.post(first_post['content'])
                db_post = db.query(Post).order_by(Post.generated_at.desc()).first()
                if db_post:
                    db_post.posted = True
                    db_post.posted_at = datetime.utcnow()
                    db_post.mastodon_url = result.get('url')
            except Exception as e:
                pass  # Don't fail workflow on posting error
        
        # Step 3: Fetch articles
        article_fetcher = ArticleFetcher(
            rss_feeds=config.rss_feeds,
            keywords=config.article_keywords,
            max_articles_per_feed=config.article_settings.get('max_articles_per_feed', 20)
        )
        articles_data = article_fetcher.get_top_articles(count=article_count)
        
        articles_fetched = 0
        for article_data in articles_data:
            existing = db.query(Article).filter(Article.url == article_data['url']).first()
            if not existing:
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
                articles_fetched += 1
        
        db.flush()
        
        # Step 4: Generate comments
        comment_max_length = config.comment_settings.get('max_length', 300)
        comment_generator = CommentGenerator(openrouter_client, notion_client, comment_max_length)
        
        articles_for_comments = []
        for article_data in articles_data[:5]:  # Limit to 5 articles
            articles_for_comments.append({
                'id': article_data.get('id'),
                'title': article_data['title'],
                'url': article_data['url'],
                'summary': article_data.get('summary'),
                'source': article_data.get('source')
            })
        
        comments_data = comment_generator.generate_comments(articles=articles_for_comments)
        
        comments_generated = 0
        for item in comments_data:
            if not item.get('comment'):
                continue
            
            article = db.query(Article).filter(Article.url == item['url']).first()
            if article:
                db_comment = Comment(
                    article_id=article.id,
                    content=item['comment'],
                    generated_at=datetime.utcnow(),
                    posted=False
                )
                db.add(db_comment)
                comments_generated += 1
        
        # Update workflow run
        workflow_run.status = "completed"
        workflow_run.completed_at = datetime.utcnow()
        workflow_run.posts_generated = posts_generated
        workflow_run.articles_fetched = articles_fetched
        workflow_run.comments_generated = comments_generated
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        workflow_run = db.query(WorkflowRun).filter(WorkflowRun.id == workflow_run_id).first()
        if workflow_run:
            workflow_run.status = "failed"
            workflow_run.error_message = str(e)
            workflow_run.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


@router.post("/full", response_model=WorkflowRunResponse, status_code=status.HTTP_202_ACCEPTED)
def run_full_workflow_endpoint(
    request: WorkflowRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_database),
    config: Config = Depends(get_app_config)
):
    """Run full automation workflow"""
    # Create workflow run record
    workflow_run = WorkflowRun(
        workflow_type="full",
        status="running",
        started_at=datetime.utcnow()
    )
    db.add(workflow_run)
    db.commit()
    db.refresh(workflow_run)
    
    # Run workflow in background
    background_tasks.add_task(
        run_full_workflow,
        workflow_run.id,
        request.post_count,
        request.article_count,
        request.post_to_mastodon,
        config
    )
    
    return WorkflowRunResponse.from_orm(workflow_run)


@router.get("/runs", response_model=list[WorkflowRunResponse])
def list_workflow_runs(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_database)
):
    """List workflow runs"""
    runs = db.query(WorkflowRun).order_by(WorkflowRun.started_at.desc()).offset(skip).limit(limit).all()
    return [WorkflowRunResponse.model_validate(r) for r in runs]


@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
def get_workflow_run(run_id: int, db: Session = Depends(get_database)):
    """Get workflow run by ID"""
    workflow_run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    
    if not workflow_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow run {run_id} not found"
        )
    
    return WorkflowRunResponse.from_orm(workflow_run)
