"""Hauptskript: durchsucht Reddit nach Keyword-Treffern und alarmiert via Telegram.

Nutzt Reddits oeffentliche, unauthentifizierte Atom/RSS-Feeds (z. B.
reddit.com/r/<sub>/new.rss) statt der offiziellen OAuth-API. Grund: Reddit hat
die Selbstregistrierung fuer neue API-Apps geschlossen (Responsible Builder
Policy, Stand 2026); der Zugriffsantrag fuer dieses persoenliche Projekt wurde
abgelehnt.

Wichtig: die frueher ueblichen `.json`-Endpunkte (z. B. `new.json`) sind
inzwischen fuer unauthentifizierte Anfragen hart geblockt (HTTP 403, auch mit
plausiblem Browser-User-Agent) - das wurde beim Bau dieses Skripts live
verifiziert. Die `.rss`-Endpunkte (Atom-Feeds) funktionieren dagegen weiterhin
mit einem ehrlichen, nicht-generischen User-Agent. Beide Varianten sind
inoffiziell/nicht supported, koennen sich jederzeit aendern und unterliegen
strengerem, undokumentiertem Rate-Limiting als die offizielle API - deshalb ist
dieses Skript defensiv gebaut: ein fehlgeschlagener oder nicht parsebarer
Request bricht den Lauf nicht ab, sondern wird uebersprungen und geloggt.

Laeuft als kurzlebiger Prozess (gedacht fuer periodische Ausfuehrung via GitHub
Actions): ein begrenzter Durchgang pro Lauf ueber die neuesten Posts/Kommentare,
Dedup ueber seen_ids.json.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from matcher import find_matches, load_keyword_groups  # noqa: E402
from notifier import send_alert  # noqa: E402

ROOT = Path(__file__).parent.parent
KEYWORDS_PATH = ROOT / "keywords.yaml"
SEEN_IDS_PATH = ROOT / "seen_ids.json"
CONFIG_PATH = ROOT / "config.yaml"

MAX_SEEN_IDS = 5000
POST_LIMIT = 100
COMMENT_LIMIT = 100
REQUEST_TIMEOUT = 15
DELAY_BETWEEN_REQUESTS = 5  # Sekunden Pause zwischen den beiden Requests, aus
# Ruecksicht auf das strengere, undokumentierte Rate-Limiting unauthentifizierter
# Zugriffe (beim Testen wurde nach mehreren schnellen Anfragen kurzzeitig ein
# HTTP 429 beobachtet; bei einem Lauf alle 45 Minuten mit nur 2 Requests ist das
# unkritisch, die Pause ist trotzdem ein guter Nachbar).

BASE_URL = "https://www.reddit.com"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
_TAG_RE = re.compile(r"<[^>]+>")


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return {}


def load_seen_ids() -> list[str]:
    if SEEN_IDS_PATH.exists():
        return json.loads(SEEN_IDS_PATH.read_text(encoding="utf-8"))
    return []


def save_seen_ids(seen_ids: list[str]) -> None:
    trimmed = seen_ids[-MAX_SEEN_IDS:]
    SEEN_IDS_PATH.write_text(json.dumps(trimmed, indent=2) + "\n", encoding="utf-8")


def target_subreddit_path(config: dict) -> str:
    if config.get("search_all", False):
        return "all"
    subreddits = config.get("subreddits") or ["all"]
    return "+".join(subreddits)


def _clean_html(raw: str) -> str:
    """Entfernt HTML-Tags und loest Entities aus Reddits <content>-Feld auf."""
    text = _TAG_RE.sub(" ", raw or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_feed(path: str, user_agent: str, limit: int) -> list[dict]:
    """Holt einen Reddit-Atom-Feed (.rss) und gibt normalisierte Eintraege zurueck.

    Gibt bei Fehlern (Netzwerk, Rate-Limit, kaputtes XML) eine leere Liste
    zurueck statt den ganzen Lauf abzubrechen - ein einzelner fehlgeschlagener
    Request soll den Rest des Durchgangs nicht verhindern.
    """
    url = f"{BASE_URL}{path}"
    headers = {"User-Agent": user_agent}
    params = {"limit": limit}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        root = ET.fromstring(response.text)
    except (requests.RequestException, ET.ParseError) as exc:
        print(f"WARNUNG: Konnte {url} nicht laden ({exc}). Ueberspringe.", file=sys.stderr)
        return []

    entries = []
    for entry in root.findall("atom:entry", ATOM_NS):
        category = entry.find("atom:category", ATOM_NS)
        link = entry.find("atom:link", ATOM_NS)
        author = entry.findtext("atom:author/atom:name", default="", namespaces=ATOM_NS)
        entries.append(
            {
                "id": entry.findtext("atom:id", default="", namespaces=ATOM_NS),
                "title": entry.findtext("atom:title", default="", namespaces=ATOM_NS),
                "subreddit": category.get("term") if category is not None else "?",
                "author": author.removeprefix("/u/") if author else None,
                "link": link.get("href") if link is not None else "",
                "content": _clean_html(entry.findtext("atom:content", default="", namespaces=ATOM_NS)),
            }
        )
    return entries


def main() -> int:
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    user_agent = os.environ["REDDIT_USER_AGENT"]
    config = load_config()
    groups = load_keyword_groups(KEYWORDS_PATH)

    seen_ids_list = load_seen_ids()
    seen_ids_set = set(seen_ids_list)

    subreddit_path = target_subreddit_path(config)
    checked_count = 0
    alert_count = 0

    # --- Posts (Titel + Body) ---
    posts = fetch_feed(f"/r/{subreddit_path}/new.rss", user_agent, POST_LIMIT)
    for post in posts:
        post_id = post["id"] or post["link"]
        if not post_id or post_id in seen_ids_set:
            continue
        seen_ids_set.add(post_id)
        seen_ids_list.append(post_id)
        checked_count += 1

        text = f"{post['title']}\n{post['content']}"
        for group_name in find_matches(text, groups):
            send_alert(
                bot_token,
                chat_id,
                keyword_group=group_name,
                subreddit=post["subreddit"],
                kind="post",
                title_or_excerpt=post["title"],
                url=post["link"],
                author=post["author"],
            )
            alert_count += 1

    time.sleep(DELAY_BETWEEN_REQUESTS)

    # --- Kommentare ---
    comments = fetch_feed(f"/r/{subreddit_path}/comments.rss", user_agent, COMMENT_LIMIT)
    for comment in comments:
        comment_id = comment["id"] or comment["link"]
        if not comment_id or comment_id in seen_ids_set:
            continue
        seen_ids_set.add(comment_id)
        seen_ids_list.append(comment_id)
        checked_count += 1

        for group_name in find_matches(comment["content"], groups):
            send_alert(
                bot_token,
                chat_id,
                keyword_group=group_name,
                subreddit=comment["subreddit"],
                kind="comment",
                title_or_excerpt=comment["content"],
                url=comment["link"],
                author=comment["author"],
            )
            alert_count += 1

    save_seen_ids(seen_ids_list)
    print(f"{checked_count} neue Items geprueft, {alert_count} Alert(s) gesendet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
