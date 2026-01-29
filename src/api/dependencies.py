"""
Shared dependencies for FastAPI routes
"""
from typing import Generator
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import get_config, Config


def get_database() -> Generator[Session, None, None]:
    """Dependency to get database session"""
    yield from get_db()


def get_app_config() -> Config:
    """Dependency to get application configuration"""
    return get_config()
