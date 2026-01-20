"""
Utility functions for TrustStack Social Media Automation
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

def setup_logging(level: str = "INFO"):
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

def save_json(data: Any, filepath: str):
    """Save data to JSON file"""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logging.info(f"Saved data to {filepath}")

def load_json(filepath: str) -> Any:
    """Load data from JSON file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def format_timestamp(dt: datetime = None) -> str:
    """Format timestamp for filenames"""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y%m%d_%H%M%S")

def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to max length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def clean_text(text: str) -> str:
    """Clean and normalize text"""
    # Remove excessive whitespace
    text = " ".join(text.split())
    return text.strip()

def extract_keywords(text: str, keywords: List[str]) -> List[str]:
    """Extract matching keywords from text"""
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]

