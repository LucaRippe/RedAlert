"""Keyword-Matching-Logik fuer den Reddit-Listener.

Laedt Gruppen aus keywords.yaml und prueft freien Text dagegen. Eine Gruppe
matcht, wenn IRGENDEINE Phrase aus match_any als Teilstring im Text vorkommt
(gross-/kleinschreibungsunabhaengig, ausser case_sensitive: true ist gesetzt)
und KEINE Phrase aus exclude_any vorkommt.

Jeder Eintrag in keywords.yaml ist entweder eine volle Gruppe (dict mit 'name'
und 'match_any', optional 'exclude_any'/'case_sensitive') oder - als Kurzform
fuer ein einzelnes Ad-hoc-Keyword ohne exclude_any-Bedarf - einfach ein nackter
String. Ein String-Eintrag wird zu einer Gruppe, deren Name die Phrase selbst
ist und die genau diese eine Phrase in match_any hat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class KeywordGroup:
    name: str
    match_any: list[str]
    exclude_any: list[str] = field(default_factory=list)
    case_sensitive: bool = False

    def matches(self, text: str) -> bool:
        haystack = text if self.case_sensitive else text.lower()
        needles = self.match_any if self.case_sensitive else [p.lower() for p in self.match_any]
        excludes = self.exclude_any if self.case_sensitive else [p.lower() for p in self.exclude_any]

        if not any(phrase in haystack for phrase in needles):
            return False
        if any(phrase in haystack for phrase in excludes):
            return False
        return True


def load_keyword_groups(path: str | Path) -> list[KeywordGroup]:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []

    groups: list[KeywordGroup] = []
    for entry in raw:
        if isinstance(entry, str):
            # Kurzform: ein nacktes Keyword ohne umgebende Gruppen-Struktur.
            groups.append(KeywordGroup(name=entry, match_any=[entry]))
            continue

        if "name" not in entry or "match_any" not in entry:
            raise ValueError(f"Ungueltige Keyword-Gruppe (braucht 'name' und 'match_any'): {entry}")
        groups.append(
            KeywordGroup(
                name=entry["name"],
                match_any=list(entry["match_any"]),
                exclude_any=list(entry.get("exclude_any", [])),
                case_sensitive=bool(entry.get("case_sensitive", False)),
            )
        )
    return groups


def find_matches(text: str, groups: list[KeywordGroup]) -> list[str]:
    """Gibt die Namen aller Keyword-Gruppen zurueck, die auf den Text matchen."""
    return [group.name for group in groups if group.matches(text)]
