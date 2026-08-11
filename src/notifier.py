"""Versand von Discord-Webhook-Benachrichtigungen."""

from __future__ import annotations

import requests

MAX_EXCERPT_LEN = 200


def _truncate(text: str, length: int = MAX_EXCERPT_LEN) -> str:
    text = text.strip()
    if len(text) <= length:
        return text
    return text[:length].rstrip() + "..."


def send_alert(
    webhook_url: str,
    *,
    keyword_group: str,
    subreddit: str,
    kind: str,  # "post" oder "comment"
    title_or_excerpt: str,
    url: str,
    author: str | None = None,
) -> None:
    """Sendet einen einzelnen Treffer als Discord-Embed."""
    embed = {
        "title": f"\U0001f514 {keyword_group}",
        "description": _truncate(title_or_excerpt),
        "url": url,
        "color": 0xFF4500,  # reddit-orange
        "fields": [
            {"name": "Subreddit", "value": f"r/{subreddit}", "inline": True},
            {"name": "Typ", "value": "Post" if kind == "post" else "Kommentar", "inline": True},
        ],
        "footer": {"text": f"u/{author}" if author else "reddit-listener"},
    }

    response = requests.post(webhook_url, json={"embeds": [embed]}, timeout=15)
    response.raise_for_status()
