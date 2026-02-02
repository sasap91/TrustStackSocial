"""
Openrouter API client for LLM interactions
"""
import logging
import os
from typing import Dict, Any, Optional, List
from openai import OpenAI


class NoLLMError(Exception):
    """Raised when NO_LLM=1 and no OpenRouter call should be made."""
    pass

# Note: IPv4 forcing is handled at socket level in main.py
# httpx (used by OpenAI library) will inherit IPv4-only behavior

# Global cap to avoid 402 Payment Required; leave headroom below account limit
MAX_TOKENS = 80

logger = logging.getLogger(__name__)


class OpenrouterClient:
    """Client for interacting with Openrouter API"""
    
    def __init__(self, api_key: str, model: str = "anthropic/claude-3.5-sonnet"):
        """
        Initialize Openrouter client
        
        Args:
            api_key: Openrouter API key
            model: Model to use (default: anthropic/claude-3.5-sonnet)
        """
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        logger.info(f"Initialized Openrouter client with model: {model}")
    
    def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate completion from Openrouter.
        Uses global MAX_TOKENS unless caller passes a lower max_tokens (e.g. for minimal token usage).
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Optional; if set and <= MAX_TOKENS, used for this call; else MAX_TOKENS
            
        Returns:
            Generated text
        """
        if os.getenv("NO_LLM") == "1":
            raise NoLLMError("NO_LLM enabled")
        effective_max = (
            min(max_tokens, MAX_TOKENS)
            if (max_tokens is not None and max_tokens > 0)
            else MAX_TOKENS
        )
        max_tokens = effective_max
        try:
            messages = []
            
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            logger.info(f"Generating completion with model: {self.model}")
            logger.debug(f"Prompt length: {len(prompt)} chars")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            content = response.choices[0].message.content
            logger.info(f"Generated completion: {len(content)} chars")
            
            return content
            
        except Exception as e:
            logger.error(f"Error generating completion: {e}")
            raise
    
    def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> List[str]:
        """
        Generate multiple completions. Each call uses MAX_TOKENS.
        
        Args:
            prompts: List of prompts
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Ignored; MAX_TOKENS is used
            
        Returns:
            List of generated texts
        """
        results = []
        
        for i, prompt in enumerate(prompts):
            logger.info(f"Generating completion {i+1}/{len(prompts)}")
            result = self.generate_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature
            )
            results.append(result)
        
        return results
    
    def generate_social_post(
        self,
        company_info: str,
        style: str = "professional",
        max_length: int = 500,
        temperature: float = 0.7
    ) -> str:
        """
        Generate a social media post
        
        Args:
            company_info: Company information to base post on
            style: Writing style (professional, casual, technical)
            max_length: Maximum post length
            temperature: Sampling temperature
            
        Returns:
            Generated social media post
        """
        system_prompt = f"""You are a social media manager for TrustStack. 
Create engaging, {style} social media posts that highlight the company's value proposition.
Posts should be concise, engaging, and under {max_length} characters."""
        
        prompt = f"""Based on the following company information, create a compelling social media post:

{company_info}

Create a {style} post that:
- Highlights a key aspect of TrustStack
- Is engaging and shareable
- Stays under {max_length} characters
- Includes relevant hashtags if appropriate

Post:"""
        
        return self.generate_completion(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature
        )
    
    def generate_article_comment(
        self,
        article_title: str,
        article_summary: str,
        company_context: str,
        max_length: int = 300,
        temperature: float = 0.7
    ) -> str:
        """
        Generate a thoughtful comment on an article
        
        Args:
            article_title: Article title
            article_summary: Article summary/excerpt
            company_context: Company context for perspective
            max_length: Maximum comment length
            temperature: Sampling temperature
            
        Returns:
            Generated comment
        """
        system_prompt = f"""You are an AI/ML expert representing TrustStack. 
Create thoughtful, insightful comments on industry articles.
Comments should add value to the discussion and stay under {max_length} characters."""
        
        prompt = f"""Article: {article_title}

Summary: {article_summary}

Company Context: {company_context}

Write a thoughtful comment that:
- Provides insightful perspective on the article
- Relates to TrustStack's expertise when relevant
- Adds value to the discussion
- Is professional and respectful
- Stays under {max_length} characters

Comment:"""
        
        return self.generate_completion(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature
        )

