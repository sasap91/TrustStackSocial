"""
Replicate API client for generating comic-style images using fine-tuned Flux model
"""
import logging
import os
import socket
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import replicate
import urllib3.util.connection

from .openrouter_client import OpenrouterClient, NoLLMError

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


class ReplicateImageGenerator:
    """Generate comic-style images using Replicate Flux fine-tuned model"""
    
    def __init__(
        self,
        replicate_api_token: str,
        openrouter_client: OpenrouterClient,
        model: str = "sundai-club/truststacksocial:b897202db67596183259c5dfaa424ddeb898cc5923934fe8afdd8e096c721517",
        trigger_word: str = "truststack",
        model_type: str = "schnell",
        num_inference_steps: int = 4,
        guidance_scale: float = 7.5,
        style_suffix: str = "cartoonish style, pastel colors",
        image_directory: str = "assets/generated_images"
    ):
        """
        Initialize Replicate image generator
        
        Args:
            replicate_api_token: Replicate API token
            openrouter_client: OpenRouter client for generating image prompts
            model: Replicate model identifier
            trigger_word: Trigger word for fine-tuned model
            model_type: Model type (schnell or dev)
            num_inference_steps: Number of inference steps
            guidance_scale: Guidance scale for generation
            style_suffix: Style suffix for prompts
            image_directory: Directory to save generated images
        """
        self.replicate_api_token = replicate_api_token
        self.openrouter_client = openrouter_client
        self.model = model
        self.trigger_word = trigger_word
        self.model_type = model_type
        self.num_inference_steps = num_inference_steps
        self.guidance_scale = guidance_scale
        self.style_suffix = style_suffix
        # Anchor to project root so comic is always saved in the same place (approval can find it)
        image_dir = Path(image_directory)
        if not image_dir.is_absolute():
            project_root = Path(__file__).resolve().parent.parent
            self.image_directory = (project_root / image_directory).resolve()
        else:
            self.image_directory = image_dir.resolve()
        
        # Set Replicate API token in environment
        os.environ["REPLICATE_API_TOKEN"] = replicate_api_token
        
        # Create image directory if it doesn't exist
        self.image_directory.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized ReplicateImageGenerator with model: {model}")
    
    def create_image_prompt(
        self,
        post_content: str,
        articles: List[Dict[str, Any]],
        quotes: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Create image generation prompt from post content and news context.
        Optionally uses LLM for a minimal-token topic from article titles; fallback to first title or default.
        """
        topic = None
        if os.getenv("NO_LLM") != "1" and articles:
            try:
                titles = []
                for a in articles[:3]:
                    t = (a.get("title") or "").strip()
                    titles.append((t[:40] + "…") if len(t) > 40 else t)
                user_prompt = "Titles: " + " | ".join(titles) + "\nTopic (3-8 words):"
                raw = self.openrouter_client.generate_completion(
                    prompt=user_prompt,
                    system_prompt=None,
                    temperature=0.5,
                    max_tokens=20
                )
                if raw:
                    topic = raw.strip().strip('"\'').strip()
            except (NoLLMError, Exception) as e:
                logger.debug("Comic topic LLM fallback: %s", e)
        if not topic:
            topic = (
                articles[0]["title"]
                if articles and articles[0].get("title")
                else "AI and online safety"
            )
        image_prompt = (
            f"A clean 3-panel comic in Truststack brand style about: {topic}. "
            "Friendly robot mascot, trust & safety theme, minimal, professional, no text."
        )
        logger.info(f"Generated image prompt: {image_prompt[:100]}...")
        return image_prompt
    
    def generate_comic_image(
        self,
        post_content: str,
        articles: List[Dict[str, Any]],
        quotes: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[str]:
        """
        Generate comic image using Replicate API
        
        Args:
            post_content: Post content for context
            articles: List of article dictionaries
            quotes: Optional list of quote dictionaries
            
        Returns:
            Image URL if successful, None otherwise
        """
        try:
            # Create image prompt
            image_prompt = self.create_image_prompt(post_content, articles, quotes)
            
            logger.info(f"Generating image with Replicate model: {self.model}")
            logger.debug(f"Image prompt: {image_prompt}")
            
            # Call Replicate API
            output = replicate.run(
                self.model,
                input={
                    "prompt": image_prompt,
                    "num_inference_steps": self.num_inference_steps,
                    "guidance_scale": self.guidance_scale,
                    "model": self.model_type
                }
            )
            
            # Replicate returns an iterator, get the first (and typically only) result
            # Convert to list to handle iterator
            output_list = list(output) if output else []
            
            if output_list and len(output_list) > 0:
                image_url = str(output_list[0])
                logger.info(f"Generated image URL: {image_url}")
                return image_url
            else:
                logger.error("Replicate API returned no output")
                return None
                
        except Exception as e:
            logger.error(f"Error generating image with Replicate: {e}")
            return None
    
    def download_image(self, url: str, save_filename: Optional[str] = None) -> Optional[str]:
        """
        Download image from URL and save locally
        
        Args:
            url: Image URL from Replicate
            save_filename: Optional filename (will generate if not provided)
            
        Returns:
            Local file path if successful, None otherwise
        """
        try:
            logger.info(f"Downloading image from: {url}")
            
            # Generate filename if not provided
            if not save_filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_filename = f"comic_{timestamp}.webp"
            
            save_path = self.image_directory / save_filename
            # Resolve to absolute so approval/Mastodon can find the file from any cwd
            save_path = save_path.resolve()
            
            # Download image
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Save to file
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Downloaded image to: {save_path}")
            
            # Validate file exists and has content; return absolute path
            if save_path.exists() and save_path.stat().st_size > 0:
                return str(save_path)
            else:
                logger.error(f"Downloaded file is empty or doesn't exist: {save_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None
    
    def generate_and_download_image(
        self,
        post_content: str,
        articles: List[Dict[str, Any]],
        quotes: Optional[List[Dict[str, Any]]] = None,
        pending_post_id: Optional[int] = None
    ) -> Optional[str]:
        """
        Generate comic image and download it locally
        
        Args:
            post_content: Post content for context
            articles: List of article dictionaries
            quotes: Optional list of quote dictionaries
            pending_post_id: Optional pending post ID for filename
            
        Returns:
            Tuple (local_path, image_url) on success; (None, None) on failure.
        """
        try:
            # Generate image
            image_url = self.generate_comic_image(post_content, articles, quotes)
            
            if not image_url:
                logger.warning("Image generation failed, returning (None, None)")
                return (None, None)
            
            # Generate filename with pending_post_id if available
            save_filename = None
            if pending_post_id:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_filename = f"comic_{pending_post_id}_{timestamp}.webp"
            
            # Download image
            local_path = self.download_image(image_url, save_filename)
            if local_path:
                return (local_path, image_url)
            return (None, None)
            
        except Exception as e:
            logger.error(f"Error in generate_and_download_image: {e}")
            return (None, None)
