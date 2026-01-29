"""
Notion API client for fetching company information
"""
import logging
import socket
import subprocess
import re
from typing import Dict, Any, Optional, Tuple, List
import httpx
from notion_client import Client
from notion_client.errors import APIResponseError

logger = logging.getLogger(__name__)

# Ensure IPv4 is forced at socket level (in case main.py hasn't patched yet)
socket.has_ipv6 = False

# Patch socket.getaddrinfo to add nslookup fallback
# Store whatever getaddrinfo is currently (might be patched by main.py)
_current_getaddrinfo = socket.getaddrinfo

def getaddrinfo_ipv4(*args, **kwargs):
    """Force IPv4-only DNS resolution with nslookup fallback"""
    # Remove IPv6 family if specified
    if len(args) >= 3:
        family = args[2]
        if family == socket.AF_UNSPEC:
            family = socket.AF_INET
        elif family == socket.AF_INET6:
            family = socket.AF_INET
        args = list(args)
        args[2] = family
        args = tuple(args)
    else:
        # Default to IPv4
        kwargs['family'] = socket.AF_INET
    
    try:
        return _current_getaddrinfo(*args, **kwargs)
    except socket.gaierror as e:
        # If DNS fails, try nslookup as fallback
        if len(args) >= 1:
            host = args[0]
            port = args[1] if len(args) >= 2 else 0
            
            # Try nslookup as fallback
            try:
                result = subprocess.run(
                    ['nslookup', host],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    # Parse nslookup output to extract IP addresses
                    ip_pattern = r'Address:\s*(\d+\.\d+\.\d+\.\d+)'
                    matches = re.findall(ip_pattern, result.stdout)
                    if matches:
                        ip = matches[0]
                        logger.info(f"Resolved {host} to {ip} via nslookup fallback")
                        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port))]
            except Exception as fallback_error:
                logger.debug(f"nslookup fallback failed: {fallback_error}")
        
        # Re-raise the original error if fallback fails
        raise

# Apply the patch
socket.getaddrinfo = getaddrinfo_ipv4


class NotionClient:
    """Client for fetching company information from Notion"""
    
    def __init__(self, api_key: str, page_id: str):
        """
        Initialize Notion client
        
        Args:
            api_key: Notion API key
            page_id: Notion page ID containing company information
        """
        # Fix 2: Force IPv4
        socket.has_ipv6 = False
        
        # Fix 1: Create explicit httpx client with trust_env=False to disable proxy inheritance
        transport = httpx.HTTPTransport(retries=3)
        http_client = httpx.Client(
            transport=transport,
            trust_env=False,  # Disables proxy inheritance and DNS overrides
            timeout=30.0,
            http2=False  # Force HTTP/1.1 (macOS security stacks can block HTTP/2)
        )
        
        self.client = Client(
            auth=api_key,
            client=http_client
        )
        self.page_id = page_id
        self._cached_content = None
    
    def fetch_page_content(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch content from Notion page
        
        Args:
            force_refresh: Force refresh cached content
            
        Returns:
            Dictionary containing page content
        """
        if self._cached_content and not force_refresh:
            logger.info("Using cached Notion content")
            return self._cached_content
        
        try:
            logger.info(f"Fetching Notion page: {self.page_id}")
            
            # Fix 3: Debug output for API host
            logger.debug("NOTION BASE HOST: api.notion.com")
            
            # Fetch page
            page = self.client.pages.retrieve(page_id=self.page_id)
            
            # Fetch blocks (page content)
            blocks = self.client.blocks.children.list(block_id=self.page_id)
            
            # Parse content
            content = self._parse_blocks(blocks.get('results', []))
            
            # Get page title
            title = self._extract_page_title(page)
            
            result = {
                'title': title,
                'content': content,
                'raw_text': self._blocks_to_text(blocks.get('results', [])),
                'properties': page.get('properties', {})
            }
            
            self._cached_content = result
            logger.info(f"Successfully fetched Notion page: {title}")
            
            return result
            
        except APIResponseError as e:
            logger.error(f"Notion API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching Notion content: {e}")
            raise
    
    def _extract_page_title(self, page: Dict) -> str:
        """Extract title from page properties"""
        properties = page.get('properties', {})
        
        # Try to find title property
        for prop_name, prop_value in properties.items():
            if prop_value.get('type') == 'title':
                title_list = prop_value.get('title', [])
                if title_list:
                    return title_list[0].get('plain_text', 'Untitled')
        
        return 'Untitled'
    
    def _parse_blocks(self, blocks: list) -> Dict[str, Any]:
        """Parse Notion blocks into structured content"""
        content = {
            'paragraphs': [],
            'headings': [],
            'lists': [],
            'quotes': []
        }
        
        for block in blocks:
            block_type = block.get('type')
            
            if block_type == 'paragraph':
                text = self._extract_text_from_block(block)
                if text:
                    content['paragraphs'].append(text)
            
            elif block_type in ['heading_1', 'heading_2', 'heading_3']:
                text = self._extract_text_from_block(block)
                if text:
                    content['headings'].append({
                        'level': int(block_type.split('_')[1]),
                        'text': text
                    })
            
            elif block_type in ['bulleted_list_item', 'numbered_list_item']:
                text = self._extract_text_from_block(block)
                if text:
                    content['lists'].append(text)
            
            elif block_type == 'quote':
                text = self._extract_text_from_block(block)
                if text:
                    content['quotes'].append(text)
        
        return content
    
    def _extract_text_from_block(self, block: Dict) -> str:
        """Extract plain text from a block"""
        block_type = block.get('type')
        block_content = block.get(block_type, {})
        rich_text = block_content.get('rich_text', [])
        
        return ''.join([text.get('plain_text', '') for text in rich_text])
    
    def _blocks_to_text(self, blocks: list) -> str:
        """Convert all blocks to plain text"""
        text_parts = []
        
        for block in blocks:
            text = self._extract_text_from_block(block)
            if text:
                text_parts.append(text)
        
        return '\n\n'.join(text_parts)
    
    def get_company_info_summary(self) -> str:
        """
        Get a formatted summary of company information
        
        Returns:
            Formatted string with company information
        """
        content = self.fetch_page_content()
        
        summary_parts = [f"# {content['title']}\n"]
        
        # Add headings and paragraphs
        parsed = content['content']
        
        for heading in parsed['headings']:
            summary_parts.append(f"\n{'#' * (heading['level'] + 1)} {heading['text']}")
        
        for paragraph in parsed['paragraphs']:
            summary_parts.append(paragraph)
        
        return '\n\n'.join(summary_parts)
    
    def clear_cache(self):
        """Clear cached content"""
        self._cached_content = None
        logger.info("Cleared Notion cache")

