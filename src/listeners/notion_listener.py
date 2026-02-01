"""
Notion API listener: poll for doc changes, re-index RAG, optionally auto-create and post.
"""
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
STATE_FILE = DATA_DIR / "notion_listener_state.json"


def _load_state() -> Dict[str, Any]:
    DATA_DIR.mkdir(exist_ok=True)
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not load Notion listener state: %s", e)
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.warning("Could not save Notion listener state: %s", e)


def check_notion_and_act(
    notion_client,
    *,
    on_change: Optional[Callable[[], None]] = None,
    reindex_rag: bool = True,
    generate_and_post: Optional[Callable[[], bool]] = None,
) -> bool:
    """
    Check Notion docs for changes (last_edited_time). If changed:
    - Call on_change() if provided
    - Re-index RAG if reindex_rag and RAG is available
    - Call generate_and_post() if provided (e.g. generate one post and post to Mastodon)
    Returns True if a change was detected and actions were run.
    """
    try:
        current = notion_client.get_docs_last_edited()
    except Exception as e:
        logger.error("Notion get_docs_last_edited failed: %s", e)
        return False
    if not current:
        return False
    state = _load_state()
    prev = state.get("last_edited", {})
    if prev == current:
        return False
    logger.info("Notion docs changed (last_edited), running actions")
    if on_change:
        try:
            on_change()
        except Exception as e:
            logger.error("on_change failed: %s", e)
    if reindex_rag:
        try:
            from ..rag import index_notion_docs
            index_notion_docs(notion_client)
        except ImportError:
            logger.debug("RAG not available, skipping reindex")
        except Exception as e:
            logger.error("RAG reindex failed: %s", e)
    if generate_and_post:
        try:
            generate_and_post()
        except Exception as e:
            logger.error("generate_and_post failed: %s", e)
    state["last_edited"] = current
    _save_state(state)
    return True


def run_notion_listener(
    notion_client,
    *,
    interval_seconds: int = 300,
    reindex_rag: bool = True,
    generate_and_post: Optional[Callable[[], bool]] = None,
    on_change: Optional[Callable[[], None]] = None,
) -> None:
    """
    Long-running loop: every interval_seconds, check Notion for changes.
    When changed: re-index RAG (if reindex_rag), optionally run generate_and_post (e.g. create one post and post).
    """
    logger.info(
        "Notion listener started (interval=%ss, reindex_rag=%s)",
        interval_seconds,
        reindex_rag,
    )
    while True:
        try:
            check_notion_and_act(
                notion_client,
                on_change=on_change,
                reindex_rag=reindex_rag,
                generate_and_post=generate_and_post,
            )
        except Exception as e:
            logger.error("Notion listener tick failed: %s", e)
        time.sleep(interval_seconds)
