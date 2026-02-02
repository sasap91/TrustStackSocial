"""
Image handler for logo management and Mastodon image preparation
"""
import logging
import os
import socket
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
import requests
import urllib3.util.connection
from PIL import Image

logger = logging.getLogger(__name__)

# Fix 5: Force IPv4 for requests library
def patched_create_connection(address, *args, **kwargs):
    """Force IPv4 by wrapping socket creation"""
    host, port = address
    err = None
    for res in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM):
        af, socktype, proto, canonname, sa = res
        sock = None
        try:
            sock = socket.socket(af, socktype, proto)
            sock.settimeout(30)
            sock.connect(sa)
            return sock
        except OSError as _:
            err = _
            if sock is not None:
                sock.close()
    if err is not None:
        raise err
    raise OSError("getaddrinfo returns an empty list")

# Patch urllib3's create_connection to force IPv4
urllib3.util.connection.create_connection = patched_create_connection


class LogoHandler:
    """Handle company logos and image preparation for Mastodon"""
    
    def __init__(self, logo_directory: str = "assets/logos", default_logo: Optional[str] = None):
        """
        Initialize logo handler
        
        Args:
            logo_directory: Directory containing logo files
            default_logo: Default logo filename
        """
        self.logo_directory = Path(logo_directory)
        self.default_logo = default_logo
        self.logo_directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized LogoHandler with directory: {logo_directory}")
    
    def get_company_logos(self) -> List[str]:
        """
        Get list of available company logos
        
        Returns:
            List of logo file paths
        """
        logos = []
        
        if not self.logo_directory.exists():
            logger.warning(f"Logo directory does not exist: {self.logo_directory}")
            return logos
        
        # Supported image formats
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
        
        for file_path in self.logo_directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                logos.append(str(file_path))
        
        logger.info(f"Found {len(logos)} logos")
        return logos
    
    def select_logo_for_post(self, style: str = "professional", style_mapping: Optional[Dict[str, str]] = None) -> Optional[str]:
        """
        Select appropriate logo for post style
        
        Args:
            style: Post style (professional, casual, technical, etc.)
            style_mapping: Optional mapping of styles to logo filenames
            
        Returns:
            Path to selected logo, or None if not found
        """
        if style_mapping and style in style_mapping:
            logo_filename = style_mapping[style]
            logo_path = self.logo_directory / logo_filename
            if logo_path.exists():
                logger.info(f"Selected logo for style '{style}': {logo_filename}")
                return str(logo_path)
        
        # Try default logo
        if self.default_logo:
            default_path = self.logo_directory / self.default_logo
            if default_path.exists():
                logger.info(f"Using default logo: {self.default_logo}")
                return str(default_path)
        
        # Get any available logo
        logos = self.get_company_logos()
        if logos:
            selected = logos[0]
            logger.info(f"Using first available logo: {selected}")
            return selected
        
        logger.warning("No logos found")
        return None
    
    def validate_image(self, image_path: str, max_size_mb: float = 10.0) -> Dict[str, Any]:
        """
        Validate image file for Mastodon
        
        Args:
            image_path: Path to image file
            max_size_mb: Maximum file size in MB
            
        Returns:
            Dictionary with validation results
        """
        result = {
            'valid': False,
            'errors': [],
            'width': None,
            'height': None,
            'size_mb': None,
            'format': None
        }
        
        try:
            # Check if file exists
            if not os.path.exists(image_path):
                result['errors'].append(f"File not found: {image_path}")
                return result
            
            # Check file size
            file_size = os.path.getsize(image_path)
            size_mb = file_size / (1024 * 1024)
            result['size_mb'] = size_mb
            
            if size_mb > max_size_mb:
                result['errors'].append(f"File too large: {size_mb:.2f}MB (max: {max_size_mb}MB)")
                return result
            
            # Validate image format
            try:
                with Image.open(image_path) as img:
                    result['width'] = img.width
                    result['height'] = img.height
                    result['format'] = img.format
                    
                    # Mastodon typically supports: JPEG, PNG, GIF, WebP
                    supported_formats = {'JPEG', 'PNG', 'GIF', 'WEBP'}
                    if img.format not in supported_formats:
                        result['errors'].append(f"Unsupported format: {img.format}")
                        return result
                    
                    # Check dimensions (Mastodon has limits, typically 4096x4096)
                    max_dimension = 4096
                    if img.width > max_dimension or img.height > max_dimension:
                        result['errors'].append(f"Image too large: {img.width}x{img.height} (max: {max_dimension}x{max_dimension})")
                        return result
                    
                    result['valid'] = True
                    
            except Exception as e:
                result['errors'].append(f"Invalid image file: {str(e)}")
                return result
                
        except Exception as e:
            result['errors'].append(f"Error validating image: {str(e)}")
        
        return result
    
    def prepare_images_for_mastodon(self, image_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Prepare and validate images for Mastodon posting
        
        Args:
            image_paths: List of image file paths or URLs
            
        Returns:
            List of prepared image dictionaries with validation results
        """
        prepared_images = []
        
        for image_path in image_paths:
            # Handle URLs
            if image_path.startswith(('http://', 'https://')):
                # Download temporarily (would need tempfile implementation)
                logger.warning(f"URL images not yet supported: {image_path}")
                continue
            
            # Validate local file
            validation = self.validate_image(image_path)
            
            if validation['valid']:
                prepared_images.append({
                    'path': image_path,
                    'width': validation['width'],
                    'height': validation['height'],
                    'size_mb': validation['size_mb'],
                    'format': validation['format']
                })
            else:
                logger.warning(f"Image validation failed for {image_path}: {validation['errors']}")
        
        logger.info(f"Prepared {len(prepared_images)}/{len(image_paths)} images for Mastodon")
        return prepared_images
    
    def download_image_from_url(self, url: str, save_path: Optional[str] = None) -> Optional[str]:
        """
        Download image from URL
        
        Args:
            url: Image URL
            save_path: Optional path to save image (defaults to logo directory)
            
        Returns:
            Path to downloaded image, or None if failed
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Determine save path
            if not save_path:
                filename = os.path.basename(urlparse(url).path)
                if not filename or '.' not in filename:
                    filename = f"downloaded_{hash(url)}.png"
                save_path = str(self.logo_directory / filename)
            
            # Save image
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Downloaded image from {url} to {save_path}")
            return save_path
            
        except Exception as e:
            logger.error(f"Error downloading image from {url}: {e}")
            return None
