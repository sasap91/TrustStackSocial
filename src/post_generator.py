"""
Social media post generator using Openrouter and Notion
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .notion_client import NotionClient
from .openrouter_client import OpenrouterClient
from .utils import truncate_text, clean_text

logger = logging.getLogger(__name__)


class PostGenerator:
    """Generate social media posts based on company information"""
    
    def __init__(
        self,
        notion_client: NotionClient,
        openrouter_client: OpenrouterClient,
        max_length: int = 500
    ):
        """
        Initialize post generator
        
        Args:
            notion_client: Notion client for fetching company info
            openrouter_client: Openrouter client for generation
            max_length: Maximum post length
        """
        self.notion_client = notion_client
        self.openrouter_client = openrouter_client
        self.max_length = max_length
        logger.info("Initialized PostGenerator")
    
    def generate_posts(
        self,
        count: int = 5,
        styles: Optional[List[str]] = None,
        temperature: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple social media posts
        
        Args:
            count: Number of posts to generate
            styles: List of styles to use (cycles through if fewer than count)
            temperature: Sampling temperature
            
        Returns:
            List of generated posts with metadata
        """
        logger.info(f"Generating {count} social media posts")
        
        # Fetch company information
        company_info = self.notion_client.get_company_info_summary()
        logger.info("Fetched company information from Notion")
        
        # Default styles
        if styles is None:
            styles = ["professional", "casual", "technical", "inspirational", "educational"]
        
        posts = []
        
        for i in range(count):
            style = styles[i % len(styles)]
            logger.info(f"Generating post {i+1}/{count} with style: {style}")
            
            try:
                post_content = self.openrouter_client.generate_social_post(
                    company_info=company_info,
                    style=style,
                    max_length=self.max_length,
                    temperature=temperature
                )
                
                # Clean and truncate
                post_content = clean_text(post_content)
                post_content = truncate_text(post_content, self.max_length)
                
                post = {
                    'id': i + 1,
                    'content': post_content,
                    'style': style,
                    'length': len(post_content),
                    'generated_at': datetime.now().isoformat(),
                    'posted': False
                }
                
                posts.append(post)
                logger.info(f"Generated post {i+1}: {len(post_content)} chars")
                
            except Exception as e:
                logger.error(f"Error generating post {i+1}: {e}")
                continue
        
        logger.info(f"Successfully generated {len(posts)} posts")
        return posts
    
    def generate_single_post(
        self,
        style: str = "professional",
        temperature: float = 0.7,
        custom_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a single social media post
        
        Args:
            style: Writing style
            temperature: Sampling temperature
            custom_context: Optional custom context instead of Notion content
            
        Returns:
            Generated post with metadata
        """
        logger.info(f"Generating single post with style: {style}")
        
        # Use custom context or fetch from Notion
        if custom_context:
            company_info = custom_context
        else:
            company_info = self.notion_client.get_company_info_summary()
        
        post_content = self.openrouter_client.generate_social_post(
            company_info=company_info,
            style=style,
            max_length=self.max_length,
            temperature=temperature
        )
        
        # Clean and truncate
        post_content = clean_text(post_content)
        post_content = truncate_text(post_content, self.max_length)
        
        return {
            'content': post_content,
            'style': style,
            'length': len(post_content),
            'generated_at': datetime.now().isoformat(),
            'posted': False
        }
    
    def refine_post(
        self,
        post_content: str,
        feedback: str,
        temperature: float = 0.7
    ) -> str:
        """
        Refine a post based on feedback
        
        Args:
            post_content: Original post content
            feedback: Feedback for refinement
            temperature: Sampling temperature
            
        Returns:
            Refined post content
        """
        prompt = f"""Original post:
{post_content}

Feedback: {feedback}

Please refine the post based on the feedback while keeping it under {self.max_length} characters.

Refined post:"""
        
        refined = self.openrouter_client.generate_completion(
            prompt=prompt,
            temperature=temperature,
            max_tokens=300
        )
        
        return truncate_text(clean_text(refined), self.max_length)

