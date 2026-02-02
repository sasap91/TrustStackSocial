"""
Enhanced post generator that incorporates news articles with quotes (optional RAG).
"""
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy.orm import Session

from .notion_client import NotionClient
from .openrouter_client import OpenrouterClient, NoLLMError
from .article_fetcher import ArticleFetcher
from .database import Article
from .utils import truncate_text, clean_text

if TYPE_CHECKING:
    from .rag.search import RAGRetriever

logger = logging.getLogger(__name__)


class EnhancedPostGenerator:
    """Generate social media posts with news context and quotes (optional RAG)."""

    def __init__(
        self,
        notion_client: NotionClient,
        openrouter_client: OpenrouterClient,
        article_fetcher: ArticleFetcher,
        max_length: int = 500,
        rag_retriever: Optional["RAGRetriever"] = None,
    ):
        """
        Initialize enhanced post generator.

        Args:
            notion_client: Notion client for fetching company info
            openrouter_client: Openrouter client for generation
            article_fetcher: Article fetcher for news
            max_length: Maximum post length
            rag_retriever: Optional RAG retriever for company context
        """
        self.notion_client = notion_client
        self.openrouter_client = openrouter_client
        self.article_fetcher = article_fetcher
        self.max_length = max_length
        self.rag_retriever = rag_retriever
        logger.info("Initialized EnhancedPostGenerator (RAG=%s)", rag_retriever is not None)
    
    def extract_quotes_from_articles(self, articles: List[Dict[str, Any]], max_quotes: int = 3) -> List[Dict[str, Any]]:
        """
        Extract quotes from articles without LLM (summary/title only).
        Keeps costs low and avoids 402 when credits are limited.
        
        Args:
            articles: List of article dictionaries
            max_quotes: Maximum number of quotes to extract (default 3)
            
        Returns:
            List of quote dictionaries with article context
        """
        quotes = []
        for a in articles[:max_quotes]:
            s = (a.get("summary") or a.get("description") or a.get("title") or "").strip()
            quote_text = truncate_text(s, 180)
            quotes.append({
                'text': quote_text,
                'article_title': a.get('title', ''),
                'article_url': a.get('url', ''),
                'article_source': a.get('source', '')
            })
        logger.info(f"Extracted {len(quotes)} quotes from articles (non-LLM)")
        return quotes

    def _get_company_context(self, style: Optional[str] = None) -> str:
        """Get company context from RAG if available, else Notion summary."""
        if self.rag_retriever:
            query = "TrustStack company information"
            if style:
                query = f"TrustStack company {style} post"
            try:
                context, results = self.rag_retriever.retrieve_context(query=query, top_k=5)
                if context and "No relevant context found" not in context and results:
                    logger.info("Using RAG context (%d chunks)", len(results))
                    return context
            except Exception as e:
                logger.warning("RAG retrieval failed, falling back to Notion: %s", e)
        return self.notion_client.get_company_info_summary()

    def _template_post(
        self,
        company_info: str,
        articles: List[Dict[str, Any]],
        quotes: List[Dict[str, Any]],
        style: str
    ) -> str:
        """Produce an integrated post without LLM: news + TrustStack story in one message."""
        a = articles[0] if articles else {}
        title = a.get("title", "AI news worth watching")
        link = a.get("link") or a.get("url", "")
        quote = (quotes[0]["text"][:80] + "…") if quotes else None
        # One seamless message: why this news matters for trust & safety, then link
        line1 = "Why this matters for trust & safety: " + title
        if quote:
            line2 = f'"{quote}"'
        else:
            line2 = "We're building TrustStack so teams can ship with scalable Trust & Safety—policy, detection, review, enforcement."
        line3 = f"Read more: {link}" if link else ""
        tags = "#TrustAndSafety #AI"
        return "\n".join([x for x in [line1, line2, line3, tags] if x]).strip()

    def generate_post_with_news(
        self,
        article_ids: Optional[List[int]] = None,
        max_articles: int = 3,
        style: str = "professional",
        temperature: float = 0.7,
        db_session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Generate post with news context and quotes
        
        Args:
            article_ids: Optional list of specific article IDs to use
            max_articles: Maximum number of articles to use
            style: Writing style
            temperature: Sampling temperature
            db_session: Optional database session
            
        Returns:
            Generated post with metadata including articles and quotes used
        """
        logger.info(f"Generating post with news (style: {style})")

        company_info = self._get_company_context(style)
        logger.info("Fetched company context for post")
        
        # Get articles
        articles = []
        if article_ids and db_session:
            # Fetch specific articles from database
            db_articles = db_session.query(Article).filter(Article.id.in_(article_ids)).all()
            articles = [{
                'id': a.id,
                'title': a.title,
                'url': a.url,
                'summary': a.summary,
                'source': a.source
            } for a in db_articles]
        else:
            # Fetch latest articles
            articles_data = self.article_fetcher.get_top_articles(
                count=max_articles,
                min_age_hours=1,
                max_age_days=7,
                db_session=db_session
            )
            articles = articles_data[:max_articles]
        
        if not articles:
            logger.warning("No articles found, generating post without news context")
            try:
                post_content = self.openrouter_client.generate_social_post(
                    company_info=company_info,
                    style=style,
                    max_length=self.max_length,
                    temperature=temperature
                )
            except Exception:
                post_content = self._template_post(company_info, [], [], style)
            post_content = clean_text(post_content)
            post_content = truncate_text(post_content, self.max_length)

            return {
                'content': post_content,
                'style': style,
                'length': len(post_content),
                'generated_at': datetime.now().isoformat(),
                'articles_used': [],
                'quotes_used': []
            }
        
        # Extract quotes from articles (non-LLM: summary/title only)
        quotes = self.extract_quotes_from_articles(articles, max_quotes=max_articles)
        
        # Shrink prompt: company first 400 chars, articles as title + link + one sentence (summary[:180])
        company = company_info[:400]
        articles_blob = "\n".join([
            f"- {a.get('title', 'Unknown')}\n  {a.get('url', '')}\n  {(a.get('summary') or '')[:180]}"
            for a in articles
        ])
        
        # Build quotes context
        quotes_text = "\n".join([
            f'"{q["text"]}" - {q["article_title"]}'
            for q in quotes
        ])
        
        # TrustStack story lens: every post should tie the news to this
        company_story = (
            "TrustStack helps teams ship faster with scalable Trust & Safety—policy, detection, review, and enforcement. "
            "Frame the post so the news clearly connects to why trust, safety, or responsible AI matters."
        )
        system_prompt = f"""You are a social media manager for TrustStack.
{company_story}
Write ONE integrated post: the news and TrustStack's story must feel like a single message—not "here's a link" but "here's why this matters for trust and safety."
Posts must be concise, {style}, and under {self.max_length} characters.
Weave in at least one short quote from the articles (in quotation marks)."""
        
        prompt = f"""Company (first 400 chars):
{company}

Articles (title, link, one sentence):
{articles_blob}

Key Quotes from Articles:
{quotes_text}

Write a single {style} post that:
1. Opens or centers on WHY this news matters for trust & safety, content moderation, or responsible AI—tie it directly to TrustStack's story (scalable T&S: policy, detection, review, enforcement).
2. Uses at least one quote from the articles (in quotation marks).
3. References the article(s) and link(s) above.
4. Reads as one seamless message (avoid generic intros like "Interesting read" without the TrustStack angle).
5. Stays under {self.max_length} characters and includes hashtags like #TrustAndSafety #AI.

Post:"""

        try:
            post_content = self.openrouter_client.generate_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature
            )
        except Exception:
            post_content = self._template_post(company_info, articles, quotes, style)

        # Clean and truncate
        post_content = clean_text(post_content)
        post_content = truncate_text(post_content, self.max_length)
        
        # Prepare article IDs and quotes for metadata
        article_ids_used = [a.get('id') for a in articles if a.get('id')]
        quotes_metadata = [{
            'quote': q['text'],
            'article_title': q['article_title'],
            'article_url': q['article_url']
        } for q in quotes]
        
        logger.info(f"Generated post with {len(article_ids_used)} articles and {len(quotes)} quotes")
        
        return {
            'content': post_content,
            'style': style,
            'length': len(post_content),
            'generated_at': datetime.now().isoformat(),
            'articles_used': article_ids_used,
            'quotes_used': quotes_metadata,
            'article_details': articles
        }
