"""
Configuration management for TrustStack Social Media Automation
"""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any

# Load environment variables
load_dotenv()

class Config:
    """Configuration manager for the application"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._load_config()
        self._load_env_vars()
    
    def _load_config(self):
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
    
    def _load_env_vars(self):
        """Load environment variables"""
        # Openrouter
        self.openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
        self.openrouter_model = os.getenv('OPENROUTER_MODEL', 'anthropic/claude-3.5-sonnet')
        
        # Notion
        self.notion_api_key = os.getenv('NOTION_API_KEY')
        self.notion_page_id = os.getenv('NOTION_PAGE_ID')
        
        # Mastodon
        self.mastodon_access_token = os.getenv('MASTODON_ACCESS_TOKEN')
        self.mastodon_api_base_url = os.getenv('MASTODON_API_BASE_URL', 'https://mastodon.social')
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
    
    @property
    def rss_feeds(self) -> list:
        """Get list of RSS feeds"""
        return self.get('rss_feeds', [])
    
    @property
    def article_keywords(self) -> list:
        """Get article filtering keywords"""
        return self.get('article_keywords', [])
    
    @property
    def article_settings(self) -> Dict[str, Any]:
        """Get article fetching settings"""
        return self.get('article_settings', {})
    
    @property
    def post_settings(self) -> Dict[str, Any]:
        """Get post generation settings"""
        return self.get('post_settings', {})
    
    @property
    def comment_settings(self) -> Dict[str, Any]:
        """Get comment generation settings"""
        return self.get('comment_settings', {})
    
    def validate(self) -> list:
        """Validate required configuration values"""
        errors = []
        
        if not self.openrouter_api_key:
            errors.append("OPENROUTER_API_KEY not set")
        
        if not self.notion_api_key:
            errors.append("NOTION_API_KEY not set")
        
        if not self.notion_page_id:
            errors.append("NOTION_PAGE_ID not set")
        
        if not self.mastodon_access_token:
            errors.append("MASTODON_ACCESS_TOKEN not set")
        
        return errors


# Global config instance
_config = None

def get_config(config_path: str = "config.yaml") -> Config:
    """Get or create global config instance"""
    global _config
    if _config is None:
        _config = Config(config_path)
    return _config

