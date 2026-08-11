"""Hauptskript: durchsucht Reddit nach Keyword-Treffern und alarmiert via Discord.

Laeuft als kurzlebiger Prozess (gedacht fuer periodische Ausfuehrung via GitHub
Actions). Statt PRAWs Streaming-Generatoren (subreddit.stream.submissions() /
.comments()) - die auf Endlosbetrieb ausgelegt sind und blockieren, bis neue
Items eintreffen - macht dieses Skript pro Lauf einen einzigen begrenzten
Durchgang ueber die neuesten Posts/Kommentare (subreddit.new() / .comments())
und verlaesst sich auf seen_ids.json fuer die Deduplizierung ueber Laeufe
hinweg. Das ist die passende Form fuer "alle N Minuten aufwachen, nachsehen
was neu ist, beenden" statt eines dauerhaft laufenden Prozesses.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import praw
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


def build_reddit_client() -> praw.Reddit:
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ["REDDIT_USER_AGENT"],
    )


def target_subreddit_name(config: dict) -> str:
    if config.get("search_all", False):
        return "all"
    subreddits = config.get("subreddits") or ["all"]
    return "+".join(subreddits)


def main() -> int:
    webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
    config = load_config()
    groups = load_keyword_groups(KEYWORDS_PATH)

    seen_ids_list = load_seen_ids()
    seen_ids_set = set(seen_ids_list)

    reddit = build_reddit_client()
    reddit.read_only = True
    subreddit = reddit.subreddit(target_subreddit_name(config))

    checked_count = 0
    alert_count = 0

    # --- Posts (Titel + Body) ---
    for submission in subreddit.new(limit=POST_LIMIT):
        if submission.id in seen_ids_set:
            continue
        seen_ids_set.add(submission.id)
        seen_ids_list.append(submission.id)
        checked_count += 1

        text = f"{submission.title}\n{submission.selftext or ''}"
        for group_name in find_matches(text, groups):
            send_alert(
                webhook_url,
                keyword_group=group_name,
                subreddit=str(submission.subreddit),
                kind="post",
                title_or_excerpt=submission.title,
                url=f"https://reddit.com{submission.permalink}",
                author=str(submission.author) if submission.author else None,
            )
            alert_count += 1

    # --- Kommentare ---
    for comment in subreddit.comments(limit=COMMENT_LIMIT):
        if comment.id in seen_ids_set:
            continue
        seen_ids_set.add(comment.id)
        seen_ids_list.append(comment.id)
        checked_count += 1

        for group_name in find_matches(comment.body or "", groups):
            send_alert(
                webhook_url,
                keyword_group=group_name,
                subreddit=str(comment.subreddit),
                kind="comment",
                title_or_excerpt=comment.body or "",
                url=f"https://reddit.com{comment.permalink}",
                author=str(comment.author) if comment.author else None,
            )
            alert_count += 1

    save_seen_ids(seen_ids_list)
    print(f"{checked_count} neue Items geprueft, {alert_count} Alert(s) gesendet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
