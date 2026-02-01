#!/usr/bin/env python3
"""
Index Notion docs into RAG DB: fetch_docs -> chunk -> embed -> save.
Run after Notion content changes. Requires NOTION_API_KEY and NOTION_PAGE_ID (or NOTION_DATABASE_ID).
"""
import os
import sys
from pathlib import Path

# Project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.config import get_config
from src.notion_client import NotionClient
from src.rag import index_notion_docs

def main():
    config = get_config()
    if not config.notion_api_key or not (config.notion_page_id or config.notion_database_id):
        print("Set NOTION_API_KEY and NOTION_PAGE_ID (or NOTION_DATABASE_ID) in .env")
        sys.exit(1)
    notion_client = NotionClient(
        config.notion_api_key,
        config.notion_page_id or "",
        database_id=config.notion_database_id,
    )
    total = index_notion_docs(notion_client)
    print(f"Indexed {total} chunks into RAG DB.")

if __name__ == "__main__":
    main()
