"""Versand von Telegram-Benachrichtigungen ueber die Bot-API."""

from __future__ import annotations

import html

import requests

MAX_EXCERPT_LEN = 200
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def _truncate(text: str, length: int = MAX_EXCERPT_LEN) -> str:
    text = text.strip()
    if len(text) <= length:
        return text
    return text[:length].rstrip() + "..."


def send_alert(
    bot_token: str,
    chat_id: str,
    *,
    keyword_group: str,
    subreddit: str,
    kind: str,  # "post" oder "comment"
    title_or_excerpt: str,
    url: str,
    author: str | None = None,
) -> None:
    """Sendet einen einzelnen Treffer als Telegram-Nachricht (HTML-formatiert)."""
    type_label = "Post" if kind == "post" else "Kommentar"
    excerpt = html.escape(_truncate(title_or_excerpt))
    author_line = f"\nvon u/{html.escape(author)}" if author else ""

    text = (
        f"\U0001f514 <b>{html.escape(keyword_group)}</b>\n"
        f"r/{html.escape(subreddit)} · {type_label}\n\n"
        f"{excerpt}{author_line}\n\n"
        f'<a href="{html.escape(url)}">Zum Beitrag</a>'
    )

    response = requests.post(
        TELEGRAM_API_URL.format(token=bot_token),
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=15,
    )
    response.raise_for_status()
