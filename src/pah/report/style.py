"""Lint for generated prose, from third_party/skills/humanizer/SKILL.md (sections 8, 12, 13, 19).

Code spans, fenced blocks, URLs and table cells holding identifiers are ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DASHES = re.compile("[\u2014\u2013]")
WORDS = (
    "additionally",
    "align with",
    "bolstered",
    "crucial",
    "deep dive",
    "delve",
    "enduring",
    "enhance",
    "garner",
    "interplay",
    "intricate",
    "meticulous",
    "meticulously",
    "pivotal",
    "quietly",
    "showcase",
    "showcasing",
    "tapestry",
    "testament",
    "underscore",
    "underscores",
    "valuable",
    "vibrant",
    "plays a key role",
    "evolving landscape",
    "setting the stage",
)
WORD_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in WORDS) + r")\b", re.IGNORECASE)
BOLD_LABEL = re.compile(r"^\s*(?:[-*]|\d+\.)\s+\*\*[^*]+\*\*\s*:")
INLINE_CODE = re.compile(r"`[^`]*`")
URL = re.compile(r"https?://\S+")


@dataclass(frozen=True)
class StyleIssue:
    line: int
    rule: str
    text: str


def lint(markdown: str) -> list[StyleIssue]:
    issues: list[StyleIssue] = []
    fenced = False
    for n, raw in enumerate(markdown.splitlines(), start=1):
        if raw.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        line = URL.sub("", INLINE_CODE.sub("", raw))
        if DASHES.search(line):
            issues.append(StyleIssue(n, "dash", raw.strip()[:120]))
        m = WORD_RE.search(line)
        if m:
            issues.append(StyleIssue(n, f"word:{m.group(1).lower()}", raw.strip()[:120]))
        if BOLD_LABEL.match(raw):
            issues.append(StyleIssue(n, "bold_label", raw.strip()[:120]))
    return issues
