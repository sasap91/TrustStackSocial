"""
Comment generator for articles using Openrouter
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .openrouter_client import OpenrouterClient
from .article_fetcher import ArticleFetcher
from .notion_client import NotionClient
from .utils import truncate_text, clean_text

logger = logging.getLogger(__name__)


class CommentGenerator:
    """Generate thoughtful comments on articles"""
    
    def __init__(
        self,
        openrouter_client: OpenrouterClient,
        notion_client: NotionClient,
        max_length: int = 300
    ):
        """
        Initialize comment generator
        
        Args:
            openrouter_client: Openrouter client for generation
            notion_client: Notion client for company context
            max_length: Maximum comment length
        """
        self.openrouter_client = openrouter_client
        self.notion_client = notion_client
        self.max_length = max_length
        logger.info("Initialized CommentGenerator")
    
    def generate_comments(
        self,
        articles: List[Dict[str, Any]],
        temperature: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Generate comments for multiple articles
        
        Args:
            articles: List of articles
            temperature: Sampling temperature
            
        Returns:
            List of articles with generated comments
        """
        logger.info(f"Generating comments for {len(articles)} articles")
        
        # Get company context
        company_context = self._get_company_context()
        
        results = []
        
        for i, article in enumerate(articles):
            logger.info(f"Generating comment {i+1}/{len(articles)}")
            
            try:
                comment = self.generate_single_comment(
                    article=article,
                    company_context=company_context,
                    temperature=temperature
                )
                
                result = {
                    **article,
                    'comment': comment,
                    'comment_generated_at': datetime.now().isoformat(),
                    'comment_length': len(comment)
                }
                
                results.append(result)
                logger.info(f"Generated comment {i+1}: {len(comment)} chars")
                
            except Exception as e:
                logger.error(f"Error generating comment {i+1}: {e}")
                results.append({
                    **article,
                    'comment': None,
                    'error': str(e)
                })
                continue
        
        logger.info(f"Successfully generated {len([r for r in results if r.get('comment')])} comments")
        return results
    
    def generate_single_comment(
        self,
        article: Dict[str, Any],
        company_context: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Generate a comment for a single article
        
        Args:
            article: Article dictionary
            company_context: Company context (fetched if not provided)
            temperature: Sampling temperature
            
        Returns:
            Generated comment
        """
        if company_context is None:
            company_context = self._get_company_context()
        
        title = article.get('title', '')
        summary = article.get('summary', '')
        
        comment = self.openrouter_client.generate_article_comment(
            article_title=title,
            article_summary=summary,
            company_context=company_context,
            max_length=self.max_length,
            temperature=temperature
        )
        
        # Clean and truncate
        comment = clean_text(comment)
        comment = truncate_text(comment, self.max_length)
        
        return comment
    
    def _get_company_context(self) -> str:
        """Get company context from Notion"""
        try:
            return self.notion_client.get_company_info_summary()
        except Exception as e:
            logger.warning(f"Failed to fetch company context: {e}")
            return "TrustStack is an AI/ML company focused on innovative solutions."
    
    def format_comment_for_mastodon(
        self,
        article: Dict[str, Any],
        comment: str,
        include_url: bool = True,
        max_length: int = 500
    ) -> str:
        """
        Format comment as Mastodon post
        
        Args:
            article: Article dictionary
            comment: Generated comment
            include_url: Include article URL
            max_length: Maximum total length
            
        Returns:
            Formatted Mastodon post
        """
        parts = []
        
        # Add comment
        parts.append(comment)
        
        # Add article reference
        if include_url:
            url = article.get('url', '')
            if url:
                parts.append(f"\n\n🔗 {url}")
        
        # Join and truncate
        post = ''.join(parts)
        post = truncate_text(post, max_length)
        
        return post
    
    def batch_format_for_mastodon(
        self,
        articles_with_comments: List[Dict[str, Any]],
        max_length: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Format multiple comments for Mastodon posting
        
        Args:
            articles_with_comments: Articles with generated comments
            max_length: Maximum post length
            
        Returns:
            List of formatted posts
        """
        formatted = []
        
        for item in articles_with_comments:
            if not item.get('comment'):
                continue
            
            post_content = self.format_comment_for_mastodon(
                article=item,
                comment=item['comment'],
                max_length=max_length
            )
            
            formatted.append({
                'article_title': item.get('title'),
                'article_url': item.get('url'),
                'comment': item['comment'],
                'mastodon_post': post_content,
                'post_length': len(post_content),
                'source': item.get('source'),
                'matched_keywords': item.get('matched_keywords', [])
            })
        
        logger.info(f"Formatted {len(formatted)} comments for Mastodon")
        return formatted
    
    def refine_comment(
        self,
        comment: str,
        feedback: str,
        temperature: float = 0.7
    ) -> str:
        """
        Refine a comment based on feedback
        
        Args:
            comment: Original comment
            feedback: Feedback for refinement
            temperature: Sampling temperature
            
        Returns:
            Refined comment
        """
        prompt = f"""Original comment:
{comment}

Feedback: {feedback}

Please refine the comment based on the feedback while keeping it under {self.max_length} characters.

Refined comment:"""
        
        refined = self.openrouter_client.generate_completion(
            prompt=prompt,
            temperature=temperature,
            max_tokens=200
        )
        
        return truncate_text(clean_text(refined), self.max_length)

