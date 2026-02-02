"""
Mastodon comments listener: poll notifications (mentions), generate replies, optionally auto-post.
"""
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def _strip_html(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(html or "", "html.parser").get_text(separator=" ").strip()
    except Exception:
        return (html or "").strip()

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
STATE_FILE = DATA_DIR / "mastodon_listener_state.json"


def _load_state() -> Dict[str, Any]:
    DATA_DIR.mkdir(exist_ok=True)
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not load Mastodon listener state: %s", e)
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.warning("Could not save Mastodon listener state: %s", e)


def process_mentions_once(
    mastodon_client,
    reply_generator,
    *,
    post_reply: bool = True,
    max_replies_per_run: int = 5,
    on_reply: Optional[Callable[[Dict, str], None]] = None,
) -> int:
    """
    Fetch new mention notifications, generate replies, optionally post.
    Uses stored last notification id to avoid re-processing.
    Returns number of replies generated (and posted if post_reply).
    """
    state = _load_state()
    since_id = state.get("last_notification_id")
    notifications = mastodon_client.get_notifications(
        since_id=since_id,
        limit=40,
        types=["mention"],
    )
    if not notifications:
        return 0
    # Process newest first; we'll store the highest id we've seen
    def _notif_id(n):
        i = n.get("id")
        if i is None:
            return 0
        try:
            return int(i)
        except (TypeError, ValueError):
            return 0
    notifications = sorted(notifications, key=_notif_id, reverse=True)
    posts_to_reply: List[Dict[str, Any]] = []
    max_id_seen = since_id
    for n in notifications:
        nid = n.get("id")
        if nid and (max_id_seen is None or nid > max_id_seen):
            max_id_seen = str(nid) if nid else max_id_seen
        status = n.get("status")
        if not status:
            continue
        raw_content = status.get("content", "")
        posts_to_reply.append({
            "id": status.get("id"),
            "content": _strip_html(raw_content) or raw_content,
            "url": status.get("url", ""),
            "created_at": status.get("created_at"),
            "account": status.get("account", {}),
        })
    if not posts_to_reply:
        if max_id_seen is not None:
            state["last_notification_id"] = str(max_id_seen)
            _save_state(state)
        return 0
    posts_to_reply = posts_to_reply[:max_replies_per_run]
    try:
        replies_data = reply_generator.generate_replies_batch(
            posts_to_reply,
            temperature=0.7,
        )
    except Exception as e:
        logger.error("Reply generation failed: %s", e)
        if max_id_seen is not None:
            state["last_notification_id"] = str(max_id_seen)
            _save_state(state)
        return 0
    count = 0
    for item, reply_data in zip(posts_to_reply, replies_data):
        if not reply_data.get("should_reply") or not reply_data.get("reply"):
            continue
        reply_text = reply_data.get("reply", "").strip()
        if not reply_text:
            continue
        status_id = item.get("id")
        if not status_id:
            continue
        if post_reply:
            try:
                mastodon_client.reply_to_status(
                    status_id=str(status_id),
                    reply_content=reply_text,
                    visibility="public",
                )
                count += 1
                if on_reply:
                    on_reply(item, reply_text)
                logger.info("Auto-replied to mention %s", status_id)
            except Exception as e:
                logger.error("Failed to post reply to %s: %s", status_id, e)
        else:
            count += 1
            if on_reply:
                on_reply(item, reply_text)
            logger.info("Would reply to %s: %s", status_id, reply_text[:80])
    if max_id_seen is not None:
        state["last_notification_id"] = str(max_id_seen)
        _save_state(state)
    return count


def run_mastodon_listener(
    mastodon_client,
    reply_generator,
    *,
    interval_seconds: int = 60,
    post_reply: bool = True,
    max_replies_per_run: int = 5,
    on_reply: Optional[Callable[[Dict, str], None]] = None,
) -> None:
    """
    Long-running loop: every interval_seconds, fetch new mentions, generate replies, optionally post.
    """
    logger.info(
        "Mastodon listener started (interval=%ss, post_reply=%s)",
        interval_seconds,
        post_reply,
    )
    while True:
        try:
            process_mentions_once(
                mastodon_client,
                reply_generator,
                post_reply=post_reply,
                max_replies_per_run=max_replies_per_run,
                on_reply=on_reply,
            )
        except Exception as e:
            logger.error("Mastodon listener tick failed: %s", e)
        time.sleep(interval_seconds)
