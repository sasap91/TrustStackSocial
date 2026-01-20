"""
Article fetcher from RSS feeds and tech blogs
"""
import logging
import feedparser
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from urllib.parse import urlparse

from .utils import extract_keywords, clean_text

logger = logging.getLogger(__name__)


class ArticleFetcher:
    """Fetch and filter articles from RSS feeds"""
    
    def __init__(
        self,
        rss_feeds: List[Dict[str, str]],
        keywords: List[str],
        max_articles_per_feed: int = 20
    ):
        """
        Initialize article fetcher
        
        Args:
            rss_feeds: List of RSS feed configurations
            keywords: Keywords for filtering articles
            max_articles_per_feed: Maximum articles to fetch per feed
        """
        self.rss_feeds = rss_feeds
        self.keywords = keywords
        self.max_articles_per_feed = max_articles_per_feed
        logger.info(f"Initialized ArticleFetcher with {len(rss_feeds)} feeds")
    
    def fetch_articles(
        self,
        min_age_hours: int = 1,
        max_age_days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Fetch articles from all RSS feeds
        
        Args:
            min_age_hours: Minimum article age in hours
            max_age_days: Maximum article age in days
            
        Returns:
            List of articles with metadata
        """
        logger.info(f"Fetching articles from {len(self.rss_feeds)} feeds")
        
        all_articles = []
        now = datetime.now()
        min_date = now - timedelta(days=max_age_days)
        max_date = now - timedelta(hours=min_age_hours)
        
        for feed_config in self.rss_feeds:
            feed_name = feed_config.get('name', 'Unknown')
            feed_url = feed_config.get('url')
            
            if not feed_url:
                logger.warning(f"No URL for feed: {feed_name}")
                continue
            
            logger.info(f"Fetching feed: {feed_name}")
            
            try:
                feed = feedparser.parse(feed_url)
                
                if feed.bozo:
                    logger.warning(f"Feed parsing error for {feed_name}: {feed.bozo_exception}")
                
                for entry in feed.entries[:self.max_articles_per_feed]:
                    article = self._parse_entry(entry, feed_name)
                    
                    if article:
                        # Check date range
                        article_date = article.get('published_date')
                        if article_date:
                            if min_date <= article_date <= max_date:
                                all_articles.append(article)
                        else:
                            # Include if no date available
                            all_articles.append(article)
                
                logger.info(f"Fetched {len([a for a in all_articles if a.get('source') == feed_name])} articles from {feed_name}")
                
            except Exception as e:
                logger.error(f"Error fetching feed {feed_name}: {e}")
                continue
        
        logger.info(f"Fetched total of {len(all_articles)} articles")
        return all_articles
    
    def _parse_entry(self, entry: Any, source: str) -> Optional[Dict[str, Any]]:
        """Parse RSS entry into article dictionary"""
        try:
            title = entry.get('title', '').strip()
            link = entry.get('link', '').strip()
            
            if not title or not link:
                return None
            
            # Get summary
            summary = entry.get('summary', entry.get('description', '')).strip()
            summary = clean_text(summary)
            
            # Parse published date
            published_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    published_date = datetime(*entry.published_parsed[:6])
                except:
                    pass
            
            # Extract matched keywords
            text_to_check = f"{title} {summary}".lower()
            matched_keywords = extract_keywords(text_to_check, self.keywords)
            
            return {
                'title': title,
                'url': link,
                'summary': summary[:500],  # Limit summary length
                'source': source,
                'published_date': published_date,
                'matched_keywords': matched_keywords,
                'relevance_score': len(matched_keywords)
            }
            
        except Exception as e:
            logger.error(f"Error parsing entry: {e}")
            return None
    
    def filter_by_keywords(
        self,
        articles: List[Dict[str, Any]],
        min_keywords: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Filter articles by keyword matches
        
        Args:
            articles: List of articles
            min_keywords: Minimum number of keyword matches
            
        Returns:
            Filtered articles
        """
        filtered = [
            article for article in articles
            if article.get('relevance_score', 0) >= min_keywords
        ]
        
        logger.info(f"Filtered {len(filtered)}/{len(articles)} articles by keywords")
        return filtered
    
    def rank_articles(
        self,
        articles: List[Dict[str, Any]],
        top_n: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Rank articles by relevance and recency
        
        Args:
            articles: List of articles
            top_n: Number of top articles to return
            
        Returns:
            Top ranked articles
        """
        # Sort by relevance score (descending) and date (descending)
        sorted_articles = sorted(
            articles,
            key=lambda x: (
                x.get('relevance_score', 0),
                x.get('published_date') or datetime.min
            ),
            reverse=True
        )
        
        top_articles = sorted_articles[:top_n]
        logger.info(f"Selected top {len(top_articles)} articles")
        
        return top_articles
    
    def get_top_articles(
        self,
        count: int = 10,
        min_age_hours: int = 1,
        max_age_days: int = 7,
        min_keywords: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Fetch and return top articles
        
        Args:
            count: Number of articles to return
            min_age_hours: Minimum article age in hours
            max_age_days: Maximum article age in days
            min_keywords: Minimum keyword matches
            
        Returns:
            Top articles
        """
        # Fetch all articles
        articles = self.fetch_articles(min_age_hours, max_age_days)
        
        # Filter by keywords
        filtered = self.filter_by_keywords(articles, min_keywords)
        
        # Rank and return top N
        top = self.rank_articles(filtered, count)
        
        logger.info(f"Retrieved {len(top)} top articles")
        return top

