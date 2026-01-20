#!/usr/bin/env python3
"""
TrustStack Social Media Automation - Main CLI
"""
import os
import sys
import click
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_config
from src.utils import setup_logging, save_json, load_json
from src.notion_client import NotionClient
from src.openrouter_client import OpenrouterClient
from src.post_generator import PostGenerator
from src.mastodon_client import MastodonClient
from src.article_fetcher import ArticleFetcher
from src.comment_generator import CommentGenerator
from src.reply_generator import ReplyGenerator

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


@click.group()
@click.pass_context
def cli(ctx):
    """TrustStack Social Media Automation Tool"""
    ctx.ensure_object(dict)
    
    try:
        config = get_config()
        ctx.obj['config'] = config
        
        # Validate configuration
        errors = config.validate()
        if errors:
            click.echo("Configuration errors found:", err=True)
            for error in errors:
                click.echo(f"  - {error}", err=True)
            click.echo("\nPlease check your .env file and ensure all required variables are set.", err=True)
            sys.exit(1)
            
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--count', '-c', default=5, help='Number of posts to generate')
@click.option('--output', '-o', default='output/posts.json', help='Output file path')
@click.option('--temperature', '-t', default=0.7, help='Sampling temperature')
@click.pass_context
def generate_posts(ctx, count, output, temperature):
    """Generate social media posts from Notion content"""
    click.echo(f"Generating {count} social media posts...")
    
    config = ctx.obj['config']
    
    # Initialize clients
    notion_client = NotionClient(config.notion_api_key, config.notion_page_id)
    openrouter_client = OpenrouterClient(config.openrouter_api_key, config.openrouter_model)
    
    # Initialize post generator
    max_length = config.post_settings.get('max_length', 500)
    post_generator = PostGenerator(notion_client, openrouter_client, max_length)
    
    # Generate posts
    posts = post_generator.generate_posts(count=count, temperature=temperature)
    
    # Save to file
    save_json(posts, output)
    
    click.echo(f"\n✓ Generated {len(posts)} posts")
    click.echo(f"✓ Saved to {output}")
    
    # Display preview
    click.echo("\nPreview of generated posts:")
    for i, post in enumerate(posts[:3], 1):
        click.echo(f"\n--- Post {i} ({post['style']}) ---")
        click.echo(post['content'][:150] + "..." if len(post['content']) > 150 else post['content'])


@cli.command()
@click.option('--file', '-f', default='output/posts.json', help='Input file with posts')
@click.option('--index', '-i', type=int, help='Post index to post (0-based)')
@click.option('--all', 'post_all', is_flag=True, help='Post all posts from file')
@click.option('--preview', is_flag=True, help='Preview without posting')
@click.pass_context
def post_to_mastodon(ctx, file, index, post_all, preview):
    """Post generated content to Mastodon"""
    config = ctx.obj['config']
    
    # Load posts
    try:
        posts = load_json(file)
    except FileNotFoundError:
        click.echo(f"Error: File not found: {file}", err=True)
        sys.exit(1)
    
    # Initialize Mastodon client
    mastodon_client = MastodonClient(
        config.mastodon_access_token,
        config.mastodon_api_base_url
    )
    
    # Determine which posts to post
    if index is not None:
        if index < 0 or index >= len(posts):
            click.echo(f"Error: Invalid index {index}. Must be 0-{len(posts)-1}", err=True)
            sys.exit(1)
        posts_to_post = [posts[index]]
    elif post_all:
        posts_to_post = posts
    else:
        # Interactive selection
        click.echo("\nAvailable posts:")
        for i, post in enumerate(posts):
            status = "✓ Posted" if post.get('posted') else "○ Not posted"
            click.echo(f"  {i}. {status} - {post['style']} ({post['length']} chars)")
        
        index = click.prompt("\nSelect post index to post", type=int)
        if index < 0 or index >= len(posts):
            click.echo(f"Error: Invalid index", err=True)
            sys.exit(1)
        posts_to_post = [posts[index]]
    
    # Post to Mastodon
    for i, post in enumerate(posts_to_post):
        content = post['content']
        
        if preview:
            click.echo(f"\n--- Preview Post ---")
            click.echo(content)
            click.echo(f"Length: {len(content)} chars")
        else:
            click.echo(f"\nPosting to Mastodon...")
            try:
                result = mastodon_client.post(content)
                click.echo(f"✓ Posted successfully!")
                click.echo(f"  URL: {result['url']}")
                
                # Update post status
                post['posted'] = True
                post['posted_at'] = result['created_at']
                post['mastodon_url'] = result['url']
                
            except Exception as e:
                click.echo(f"✗ Error posting: {e}", err=True)
    
    # Save updated posts
    if not preview:
        save_json(posts, file)
        click.echo(f"\n✓ Updated {file}")


@cli.command()
@click.option('--count', '-c', default=10, help='Number of top articles to fetch')
@click.option('--output', '-o', default='output/articles.json', help='Output file path')
@click.option('--min-age-hours', default=1, help='Minimum article age in hours')
@click.option('--max-age-days', default=7, help='Maximum article age in days')
@click.pass_context
def fetch_articles(ctx, count, output, min_age_hours, max_age_days):
    """Fetch top articles from tech blogs"""
    click.echo(f"Fetching top {count} AI/ML articles...")
    
    config = ctx.obj['config']
    
    # Initialize article fetcher
    article_fetcher = ArticleFetcher(
        rss_feeds=config.rss_feeds,
        keywords=config.article_keywords,
        max_articles_per_feed=config.article_settings.get('max_articles_per_feed', 20)
    )
    
    # Fetch articles
    articles = article_fetcher.get_top_articles(
        count=count,
        min_age_hours=min_age_hours,
        max_age_days=max_age_days
    )
    
    # Save to file
    save_json(articles, output)
    
    click.echo(f"\n✓ Fetched {len(articles)} articles")
    click.echo(f"✓ Saved to {output}")
    
    # Display preview
    click.echo("\nTop articles:")
    for i, article in enumerate(articles[:5], 1):
        click.echo(f"\n{i}. {article['title']}")
        click.echo(f"   Source: {article['source']}")
        click.echo(f"   Keywords: {', '.join(article['matched_keywords'][:3])}")
        click.echo(f"   URL: {article['url']}")


@cli.command()
@click.option('--file', '-f', default='output/articles.json', help='Input file with articles')
@click.option('--output', '-o', default='output/comments.json', help='Output file path')
@click.option('--temperature', '-t', default=0.7, help='Sampling temperature')
@click.pass_context
def generate_comments(ctx, file, output, temperature):
    """Generate comments for articles"""
    click.echo(f"Generating comments for articles...")
    
    config = ctx.obj['config']
    
    # Load articles
    try:
        articles = load_json(file)
    except FileNotFoundError:
        click.echo(f"Error: File not found: {file}", err=True)
        sys.exit(1)
    
    # Initialize clients
    notion_client = NotionClient(config.notion_api_key, config.notion_page_id)
    openrouter_client = OpenrouterClient(config.openrouter_api_key, config.openrouter_model)
    
    # Initialize comment generator
    max_length = config.comment_settings.get('max_length', 300)
    comment_generator = CommentGenerator(openrouter_client, notion_client, max_length)
    
    # Generate comments
    articles_with_comments = comment_generator.generate_comments(
        articles=articles,
        temperature=temperature
    )
    
    # Save to file
    save_json(articles_with_comments, output)
    
    click.echo(f"\n✓ Generated comments for {len(articles_with_comments)} articles")
    click.echo(f"✓ Saved to {output}")
    
    # Display preview
    click.echo("\nPreview of generated comments:")
    for i, item in enumerate(articles_with_comments[:3], 1):
        if item.get('comment'):
            click.echo(f"\n--- Article {i} ---")
            click.echo(f"Title: {item['title']}")
            click.echo(f"Comment: {item['comment'][:100]}...")


@cli.command()
@click.option('--file', '-f', default='output/comments.json', help='Input file with comments')
@click.option('--index', '-i', type=int, help='Comment index to post (0-based)')
@click.option('--preview', is_flag=True, help='Preview without posting')
@click.pass_context
def post_comments(ctx, file, index, preview):
    """Post generated comments to Mastodon"""
    config = ctx.obj['config']
    
    # Load comments
    try:
        items = load_json(file)
    except FileNotFoundError:
        click.echo(f"Error: File not found: {file}", err=True)
        sys.exit(1)
    
    # Filter items with comments
    items_with_comments = [item for item in items if item.get('comment')]
    
    if not items_with_comments:
        click.echo("Error: No comments found in file", err=True)
        sys.exit(1)
    
    # Initialize clients
    notion_client = NotionClient(config.notion_api_key, config.notion_page_id)
    openrouter_client = OpenrouterClient(config.openrouter_api_key, config.openrouter_model)
    mastodon_client = MastodonClient(
        config.mastodon_access_token,
        config.mastodon_api_base_url
    )
    
    max_length = config.comment_settings.get('max_length', 300)
    comment_generator = CommentGenerator(openrouter_client, notion_client, max_length)
    
    # Format for Mastodon
    formatted = comment_generator.batch_format_for_mastodon(items_with_comments)
    
    # Select item to post
    if index is not None:
        if index < 0 or index >= len(formatted):
            click.echo(f"Error: Invalid index {index}. Must be 0-{len(formatted)-1}", err=True)
            sys.exit(1)
        items_to_post = [formatted[index]]
    else:
        # Interactive selection
        click.echo("\nAvailable comments:")
        for i, item in enumerate(formatted):
            click.echo(f"  {i}. {item['article_title'][:60]}...")
            click.echo(f"     Source: {item['source']}")
        
        index = click.prompt("\nSelect comment index to post", type=int)
        if index < 0 or index >= len(formatted):
            click.echo(f"Error: Invalid index", err=True)
            sys.exit(1)
        items_to_post = [formatted[index]]
    
    # Post to Mastodon
    for item in items_to_post:
        content = item['mastodon_post']
        
        if preview:
            click.echo(f"\n--- Preview ---")
            click.echo(f"Article: {item['article_title']}")
            click.echo(f"\n{content}")
            click.echo(f"\nLength: {item['post_length']} chars")
        else:
            click.echo(f"\nPosting comment to Mastodon...")
            try:
                result = mastodon_client.post(content)
                click.echo(f"✓ Posted successfully!")
                click.echo(f"  URL: {result['url']}")
            except Exception as e:
                click.echo(f"✗ Error posting: {e}", err=True)


@cli.command()
@click.option('--post-count', default=3, help='Number of posts to generate')
@click.option('--article-count', default=5, help='Number of articles to fetch')
@click.option('--post-to-mastodon', is_flag=True, help='Actually post to Mastodon (default: preview only)')
@click.pass_context
def full_workflow(ctx, post_count, article_count, post_to_mastodon):
    """Run the complete automation workflow"""
    click.echo("=" * 60)
    click.echo("TrustStack Social Media Automation - Full Workflow")
    click.echo("=" * 60)
    
    config = ctx.obj['config']
    
    # Step 1: Generate posts
    click.echo("\n[Step 1/4] Generating social media posts...")
    ctx.invoke(generate_posts, count=post_count, output='output/posts.json')
    
    # Step 2: Post to Mastodon (first post only, if enabled)
    if post_to_mastodon:
        click.echo("\n[Step 2/4] Posting to Mastodon...")
        ctx.invoke(post_to_mastodon, file='output/posts.json', index=0, preview=False)
    else:
        click.echo("\n[Step 2/4] Skipping Mastodon posting (use --post-to-mastodon to enable)")
    
    # Step 3: Fetch articles
    click.echo("\n[Step 3/4] Fetching top articles...")
    ctx.invoke(fetch_articles, count=article_count, output='output/articles.json')
    
    # Step 4: Generate comments
    click.echo("\n[Step 4/4] Generating comments...")
    ctx.invoke(generate_comments, file='output/articles.json', output='output/comments.json')
    
    click.echo("\n" + "=" * 60)
    click.echo("✓ Workflow complete!")
    click.echo("=" * 60)
    click.echo("\nGenerated files:")
    click.echo("  - output/posts.json (social media posts)")
    click.echo("  - output/articles.json (top articles)")
    click.echo("  - output/comments.json (article comments)")
    click.echo("\nNext steps:")
    click.echo("  - Review generated posts: cat output/posts.json")
    click.echo("  - Post to Mastodon: python main.py post-to-mastodon")
    click.echo("  - Post comments: python main.py post-comments")


@cli.command()
@click.pass_context
def account_info(ctx):
    """Display Mastodon account information"""
    config = ctx.obj['config']
    
    mastodon_client = MastodonClient(
        config.mastodon_access_token,
        config.mastodon_api_base_url
    )
    
    info = mastodon_client.get_account_info()
    
    click.echo("\nMastodon Account Information:")
    click.echo(f"  Username: @{info['username']}")
    click.echo(f"  Display Name: {info['display_name']}")
    click.echo(f"  Followers: {info['followers_count']}")
    click.echo(f"  Following: {info['following_count']}")
    click.echo(f"  Posts: {info['statuses_count']}")
    click.echo(f"  URL: {info['url']}")


@cli.command()
@click.option('--keyword', '-k', help='Keyword to search for (defaults to business-related terms)')
@click.option('--count', '-c', default=5, help='Number of posts to find')
@click.option('--output', '-o', default='output/replies.json', help='Output file path')
@click.option('--post-replies', is_flag=True, help='Actually post the replies to Mastodon')
@click.pass_context
def search_and_reply(ctx, keyword, count, output, post_replies):
    """Search for relevant posts and generate replies using structured outputs"""
    config = ctx.obj['config']
    
    # Default keywords if not provided
    if not keyword:
        keywords = ['ecommerce fraud', 'marketplace safety', 'trust and safety', 'payment fraud', 'account takeover']
        keyword = keywords[0]  # Use first one
        click.echo(f"Using default keyword: {keyword}")
    
    click.echo(f"\nSearching Mastodon for: '{keyword}'")
    click.echo(f"Looking for {count} recent posts...")
    
    # Initialize clients
    mastodon_client = MastodonClient(
        config.mastodon_access_token,
        config.mastodon_api_base_url
    )
    
    # Get account info to filter out own posts
    account_info = mastodon_client.get_account_info()
    account_id = account_info['id']
    
    # Search for posts
    posts = mastodon_client.search_posts(
        query=keyword,
        limit=count,
        account_id=account_id
    )
    
    if not posts:
        click.echo("\n✗ No relevant posts found. Try a different keyword.")
        return
    
    click.echo(f"\n✓ Found {len(posts)} posts")
    
    # Display found posts
    click.echo("\nPosts found:")
    for i, post in enumerate(posts, 1):
        click.echo(f"\n{i}. @{post['account']['username']}")
        click.echo(f"   {post['content'][:100]}...")
        click.echo(f"   URL: {post['url']}")
    
    # Initialize AI clients
    notion_client = NotionClient(config.notion_api_key, config.notion_page_id)
    openrouter_client = OpenrouterClient(config.openrouter_api_key, config.openrouter_model)
    
    # Generate replies using structured outputs
    click.echo(f"\n🤖 Generating replies using AI structured outputs...")
    
    reply_generator = ReplyGenerator(openrouter_client, notion_client, max_length=500)
    
    posts_with_replies = reply_generator.generate_replies_batch(
        posts=posts,
        temperature=0.7
    )
    
    # Save to file
    save_json(posts_with_replies, output)
    click.echo(f"\n✓ Saved replies to {output}")
    
    # Display generated replies
    click.echo("\n" + "="*60)
    click.echo("Generated Replies:")
    click.echo("="*60)
    
    replies_to_post = []
    for i, item in enumerate(posts_with_replies, 1):
        click.echo(f"\n--- Post {i} ---")
        click.echo(f"Author: @{item['account']['username']}")
        click.echo(f"Original: {item['content'][:80]}...")
        click.echo(f"Should Reply: {'✓ YES' if item.get('should_reply') else '✗ NO'}")
        click.echo(f"Reason: {item.get('reason', 'N/A')}")
        
        if item.get('should_reply') and item.get('reply'):
            click.echo(f"\nReply ({item['reply_length']} chars):")
            click.echo(f"  {item['reply']}")
            replies_to_post.append(item)
    
    # Post replies if requested
    if post_replies and replies_to_post:
        click.echo(f"\n" + "="*60)
        click.echo(f"Posting {len(replies_to_post)} replies to Mastodon...")
        click.echo("="*60)
        
        for i, item in enumerate(replies_to_post, 1):
            try:
                click.echo(f"\n[{i}/{len(replies_to_post)}] Replying to @{item['account']['username']}...")
                
                result = mastodon_client.reply_to_status(
                    status_id=item['id'],
                    reply_content=item['reply'],
                    visibility='public'
                )
                
                click.echo(f"  ✓ Posted: {result['url']}")
                
                # Brief pause between replies
                import time
                if i < len(replies_to_post):
                    time.sleep(2)
                
            except Exception as e:
                click.echo(f"  ✗ Error: {e}", err=True)
        
        click.echo(f"\n✓ Posted {len(replies_to_post)} replies!")
    
    elif not post_replies:
        click.echo(f"\n💡 To actually post these replies, run with --post-replies flag")
    
    else:
        click.echo(f"\n✗ No relevant posts to reply to")


if __name__ == '__main__':
    cli(obj={})

