#!/usr/bin/env python3
"""
One-off migration: add comic_media_url column to pending_posts.
Run from project root: python scripts/add_comic_media_url_column.py
"""
import sys
from pathlib import Path

# Add project root so we can import src.database
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from src.database import get_engine


def main():
    engine = get_engine()
    sql = "ALTER TABLE pending_posts ADD COLUMN comic_media_url TEXT;"
    with engine.begin() as conn:
        try:
            conn.execute(text(sql))
            print("Added column comic_media_url to pending_posts.")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("Column comic_media_url already exists, skipping.")
            else:
                raise


if __name__ == "__main__":
    main()
