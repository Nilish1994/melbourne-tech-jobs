"""Deterministic skill extraction from a job's title and description.

No model calls: the same text always yields the same skills, which keeps the
analytics reproducible and the tests exact. Each alias must stand alone as a
token: it may not touch a letter, digit or one of "+#." on the left, nor a
letter, digit or "+#" on the right. That keeps "Java" out of "JavaScript",
"SQL" out of "MySQL" and "C#" out of "C##" while still matching "Node.js,".
"""
from functools import lru_cache
import re

from app.skills.catalog import SKILLS

_LEFT = r"(?<![\w+#.])"
_RIGHT = r"(?![\w+#])"


@lru_cache(maxsize=1)
def _patterns() -> list[tuple[str, re.Pattern]]:
    compiled = []
    for skill, (_group, aliases) in SKILLS.items():
        alternatives = "|".join(f"(?:{alias})" for alias in aliases)
        compiled.append((skill, re.compile(f"{_LEFT}(?:{alternatives}){_RIGHT}", re.IGNORECASE)))
    return compiled


def _clean(text: str) -> str:
    # Collapse whitespace so multi-word aliases match across line breaks.
    return " ".join(text.split())


def extract_skills(*texts: str | None) -> list[str]:
    """Return the sorted canonical skills mentioned in any of the given texts."""
    combined = _clean(" \n ".join(t for t in texts if t))
    if not combined:
        return []
    return sorted(skill for skill, pattern in _patterns() if pattern.search(combined))


def skill_group(skill: str) -> str | None:
    entry = SKILLS.get(skill)
    return entry[0] if entry else None
