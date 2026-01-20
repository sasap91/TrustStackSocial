"""
Reply generator for Mastodon posts using structured outputs
"""
import logging
from typing import List, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup

from .openrouter_client import OpenrouterClient
from .notion_client import NotionClient
from .utils import clean_text, truncate_text

logger = logging.getLogger(__name__)


class ReplyGenerator:
    """Generate replies to Mastodon posts using structured outputs"""
    
    def __init__(
        self,
        openrouter_client: OpenrouterClient,
        notion_client: NotionClient,
        max_length: int = 500
    ):
        """
        Initialize reply generator
        
        Args:
            openrouter_client: Openrouter client for generation
            notion_client: Notion client for company context
            max_length: Maximum reply length
        """
        self.openrouter_client = openrouter_client
        self.notion_client = notion_client
        self.max_length = max_length
        logger.info("Initialized ReplyGenerator")
    
    def clean_html(self, html_text: str) -> str:
        """Remove HTML tags from text"""
        try:
            soup = BeautifulSoup(html_text, 'html.parser')
            return soup.get_text()
        except:
            return html_text
    
    def generate_replies_batch(
        self,
        posts: List[Dict[str, Any]],
        temperature: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Generate replies for multiple posts using structured outputs
        
        Args:
            posts: List of posts to reply to
            temperature: Sampling temperature
            
        Returns:
            List of posts with generated replies
        """
        logger.info(f"Generating replies for {len(posts)} posts")
        
        # Get company context
        company_context = self._get_company_context()
        
        # Create batch prompt with structured output format
        batch_prompt = self._create_batch_prompt(posts, company_context)
        
        system_prompt = """You are a social media manager for TrustStack, an e-commerce trust & safety company.
Generate helpful, engaging replies to posts that are relevant to TrustStack's expertise.

IMPORTANT GUIDELINES:
- Be genuinely helpful and add value to the conversation
- Don't be overly promotional - focus on insights and expertise
- Keep replies concise (under 400 chars each)
- Be professional but friendly
- Only mention TrustStack if naturally relevant
- Avoid generic responses

Generate replies as a JSON array with this structure:
[
  {
    "post_index": 0,
    "reply": "Your thoughtful reply here",
    "should_reply": true/false,
    "reason": "Why replying or not"
  }
]"""
        
        try:
            # Generate all replies at once
            response = self.openrouter_client.generate_completion(
                prompt=batch_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=2000
            )
            
            # Parse structured output
            import json
            
            # Extract JSON from response (handle markdown code blocks)
            response_clean = response.strip()
            if response_clean.startswith('```'):
                # Remove markdown code block markers
                lines = response_clean.split('\n')
                response_clean = '\n'.join(lines[1:-1])
            
            replies_data = json.loads(response_clean)
            
            # Combine with original posts
            results = []
            for post_idx, post in enumerate(posts):
                # Find matching reply
                reply_data = next(
                    (r for r in replies_data if r.get('post_index') == post_idx),
                    None
                )
                
                if reply_data and reply_data.get('should_reply'):
                    reply_text = clean_text(reply_data.get('reply', ''))
                    reply_text = truncate_text(reply_text, self.max_length)
                    
                    results.append({
                        **post,
                        'reply': reply_text,
                        'should_reply': True,
                        'reason': reply_data.get('reason', ''),
                        'reply_length': len(reply_text),
                        'generated_at': datetime.now().isoformat()
                    })
                else:
                    results.append({
                        **post,
                        'reply': None,
                        'should_reply': False,
                        'reason': reply_data.get('reason', 'Not relevant') if reply_data else 'Not relevant',
                        'generated_at': datetime.now().isoformat()
                    })
                
                logger.info(f"Post {post_idx + 1}: {'Will reply' if reply_data and reply_data.get('should_reply') else 'Skip'}")
            
            logger.info(f"Generated {len([r for r in results if r.get('should_reply')])} replies")
            return results
            
        except Exception as e:
            logger.error(f"Error generating batch replies: {e}")
            # Fallback to individual generation
            return self._generate_replies_individual(posts, company_context, temperature)
    
    def _create_batch_prompt(self, posts: List[Dict[str, Any]], company_context: str) -> str:
        """Create a batch prompt for structured output"""
        prompt_parts = [
            f"Company Context:\n{company_context}\n",
            "\nPosts to reply to:\n"
        ]
        
        for idx, post in enumerate(posts):
            content = self.clean_html(post.get('content', ''))
            author = post.get('account', {}).get('username', 'unknown')
            
            prompt_parts.append(
                f"\n--- Post {idx} ---\n"
                f"Author: @{author}\n"
                f"Content: {content}\n"
            )
        
        prompt_parts.append(
            "\nGenerate replies for each post. For each post, decide if it's relevant to TrustStack's expertise "
            "and worth replying to. If yes, create a thoughtful, helpful reply. If no, explain why.\n\n"
            "Output as JSON array:"
        )
        
        return ''.join(prompt_parts)
    
    def _generate_replies_individual(
        self,
        posts: List[Dict[str, Any]],
        company_context: str,
        temperature: float
    ) -> List[Dict[str, Any]]:
        """Fallback: Generate replies individually"""
        logger.info("Using individual reply generation (fallback)")
        
        results = []
        
        for idx, post in enumerate(posts):
            try:
                content = self.clean_html(post.get('content', ''))
                
                prompt = f"""Company Context: {company_context}

Post to reply to:
Author: @{post.get('account', {}).get('username', 'unknown')}
Content: {content}

Should we reply to this post? If yes, generate a helpful, engaging reply (under 400 chars).
If no, explain why not.

Reply:"""
                
                response = self.openrouter_client.generate_completion(
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=300
                )
                
                reply_text = clean_text(response)
                reply_text = truncate_text(reply_text, self.max_length)
                
                results.append({
                    **post,
                    'reply': reply_text,
                    'should_reply': True,
                    'reason': 'Relevant to expertise',
                    'reply_length': len(reply_text),
                    'generated_at': datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Error generating reply for post {idx}: {e}")
                results.append({
                    **post,
                    'reply': None,
                    'should_reply': False,
                    'reason': f'Error: {str(e)}'
                })
        
        return results
    
    def _get_company_context(self) -> str:
        """Get company context from Notion"""
        try:
            return self.notion_client.get_company_info_summary()
        except Exception as e:
            logger.warning(f"Failed to fetch company context: {e}")
            return "TrustStack is an e-commerce trust & safety company helping mid-sized marketplaces combat fraud and abuse."

