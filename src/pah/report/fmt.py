"""Number and value display shared by the HTML and Markdown reports (docs/UI.md, Number display).

Every function returns plain text, or None for a value the run did not produce; the renderer
decides how a missing value looks (a muted en dash in HTML, `n/a` in Markdown).
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any

THIN = "\u2009"
TIMES = "\u00d7"
GATES = ("pass", "warn", "stop", "skip")


def number(value: object, unit: str | None = None) -> str | None:
    """`2.1 Å`, `412 ms`: unit after a thin space; floats to at most two decimals."""
    if value is None:
        return None
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, int):
        text = str(value)
    elif isinstance(value, float):
        if value.is_integer() and abs(value) < 1e15:
            text = str(int(value))
        else:
            digits = 2 if abs(value) < 10 else 1 if abs(value) < 1000 else 0
            text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    else:
        text = str(value)
    return f"{text}{THIN}{unit}" if unit else text


def duration(ms: object) -> str | None:
    """Below 1 s in ms, otherwise seconds to one decimal."""
    if not isinstance(ms, (int, float)) or isinstance(ms, bool):
        return None
    return f"{round(ms)}{THIN}ms" if ms < 1000 else f"{ms / 1000:.1f}{THIN}s"


def fraction(part: object, whole: object) -> str | None:
    if part is None:
        return None
    return f"{part}/{whole}" if whole is not None else str(part)


def sha12(sha: object) -> str | None:
    return str(sha)[:12] if sha else None


def when(iso: object) -> str | None:
    """`2026-10-01 09:30:00 UTC` from an ISO timestamp."""
    if not iso:
        return None
    try:
        ts = datetime.fromisoformat(str(iso))
    except ValueError:
        return str(iso)
    return ts.strftime("%Y-%m-%d %H:%M:%S") + (" UTC" if ts.utcoffset() is not None else "")


def counts(c: Mapping[str, int]) -> list[tuple[str, int]]:
    """Gate counts in fixed order; zeros kept (the renderer mutes them)."""
    out = [(g, int(c.get(g, 0))) for g in GATES]
    out += [(g, int(c[g])) for g in ("reported", "pending") if c.get(g)]
    return out


def counts_text(c: Mapping[str, int]) -> str:
    return " · ".join(f"{g} {n}" for g, n in counts(c))


def median(values: Iterable[object]) -> float | None:
    nums = [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return statistics.median(nums) if nums else None


def _match(measurements: Sequence[Mapping[str, Any]], name: str) -> Mapping[str, Any] | None:
    for m in measurements:
        if m.get("name") == name:
            return m
    for m in measurements:
        mname = str(m.get("name", ""))
        if mname and (name.startswith(mname) or mname.startswith(name)):
            return m
    return None


def compare(check: Mapping[str, Any]) -> str | None:
    """`measured cmp threshold` for the first threshold, e.g. `undefined 1 == 0`."""
    thresholds = check.get("thresholds") or []
    if not thresholds:
        return None
    t = thresholds[0]
    m = _match(check.get("measurements") or [], str(t.get("name", "")))
    limit = number(t.get("value"))
    if m is None:
        return f"{t.get('name')} {t.get('comparator')} {limit}"
    return f"{m.get('name')} {number(m.get('value'), m.get('unit'))} {t.get('comparator')} {limit}"


def label(name: str) -> str:
    return name.replace("_", " ")
