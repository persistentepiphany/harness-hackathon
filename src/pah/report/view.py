"""Report view model: the `UiRunRecord.stats` blocks as tables and key-value cards.

The HTML and Markdown writers render the same blocks, so both reports show the same values in the
same order. Each block builder is registered with `@block` and returns None when the stats block
it reads is absent, so a block the harness did not compute never appears.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pah.report import fmt


@dataclass(frozen=True)
class Cell:
    text: str | None
    state: str | None = None
    title: str | None = None
    sub: str | None = None


@dataclass(frozen=True)
class Row:
    cells: tuple[Cell, ...]
    state: str | None = None
    rule: bool = False


@dataclass(frozen=True)
class Table:
    id: str
    title: str
    columns: tuple[str, ...]
    rows: tuple[Row, ...]
    layer: int
    numeric: tuple[bool, ...] = ()
    footer: Row | None = None
    summary: str | None = None
    caption: str | None = None
    style: str = "table"
    """table, grid (one test per cell) or matrix (method by method)."""


@dataclass(frozen=True)
class Card:
    id: str
    title: str
    rows: tuple[tuple[str, Cell], ...]
    layer: int


Block = Table | Card
Builder = Callable[[Mapping[str, Any]], Block | None]
BUILDERS: list[Builder] = []


def block(fn: Builder) -> Builder:
    BUILDERS.append(fn)
    return fn


def stats_blocks(stats: Mapping[str, Any], layer: int | None = None) -> list[Block]:
    out = [b for b in (fn(stats) for fn in BUILDERS) if b is not None]
    return [b for b in out if layer is None or b.layer == layer]


def _c(value: object, unit: str | None = None, **kw: Any) -> Cell:
    return Cell(fmt.number(value, unit), **kw)


def _rows(value: object) -> list[Mapping[str, Any]]:
    return [v for v in value if isinstance(v, Mapping)] if isinstance(value, list) else []


@block
def docking(stats: Mapping[str, Any]) -> Block | None:
    d = stats.get("docking")
    if not isinstance(d, Mapping) or not d.get("rows"):
        return None
    title = f"Docking · {d['tool']}" if d.get("tool") else "Docking"
    rows = tuple((str(k), Cell(str(v))) for k, v in d["rows"])
    return Card("docking", title, rows, layer=2)


@block
def posebusters(stats: Mapping[str, Any]) -> Block | None:
    tests = _rows(stats.get("posebusters"))
    if not tests:
        return None
    passed = sum(1 for t in tests if t.get("pass") is True)
    rows = tuple(
        Row(
            (
                Cell(str(t.get("test", ""))),
                Cell(
                    "pass" if t.get("pass") else "fail", state="pass" if t.get("pass") else "stop"
                ),
                Cell(str(t["value"]) if t.get("value") is not None else None),
            ),
            state="pass" if t.get("pass") else "stop",
        )
        for t in tests
    )
    return Table(
        "posebusters",
        "PoseBusters",
        ("test", "result", "value"),
        rows,
        layer=4,
        summary=f"{passed}/{len(tests)} tests pass",
        style="grid",
    )


Getter = Callable[[Mapping[str, Any]], str | None]


def _get(key: str) -> Getter:
    return lambda r: fmt.number(r.get(key))


def _frac(key: str, total: str) -> Getter:
    return lambda r: fmt.fraction(r.get(key), r.get(total))


PHYSICS: tuple[tuple[str, str, Getter], ...] = (
    ("drift", "drift \u00c5", _get("drift")),
    ("converged", "converged", _get("converged")),
    ("torsions", "unlikely torsions", _frac("torsions", "torsionsTotal")),
    ("clashes", "clashes", _get("clashes")),
    ("clashscore", "clashscore", _get("clashscore")),
    ("unsatisfied", "unsat. polars", _get("unsatisfied")),
    ("buriedCharged", "buried charged", _get("buriedCharged")),
    ("pbPassed", "PoseBusters", _frac("pbPassed", "pbTotal")),
)


@block
def physics(stats: Mapping[str, Any]) -> Block | None:
    rows = _rows(stats.get("physics"))
    if not rows:
        return None
    cols = [c for c in PHYSICS if any(c[0] in r for r in rows)]
    has_seed = any("seed" in r for r in rows)
    body = tuple(
        Row(
            (
                Cell(str(r.get("pose"))),
                *((_c(r.get("seed")),) if has_seed else ()),
                *(Cell(get(r)) for _, _, get in cols),
            )
        )
        for r in rows
    )
    footer_cells = [Cell("median")] + ([Cell(None)] if has_seed else [])
    for key, _, _ in cols:
        if key == "converged":
            footer_cells.append(Cell(None))
            continue
        med = fmt.median(r.get(key) for r in rows)
        totals = {r.get("pbTotal") for r in rows} if key == "pbPassed" else set()
        text = fmt.number(med)
        if key == "pbPassed" and len(totals) == 1 and text is not None:
            text = f"{text}/{totals.pop()}"
        footer_cells.append(Cell(text))
    columns = ("pose", *(("seed",) if has_seed else ()), *(name for _, name, _ in cols))
    return Table(
        "physics",
        "Per-pose physical checks",
        columns,
        body,
        layer=4,
        numeric=(False, *([True] * (len(columns) - 1))),
        footer=Row(tuple(footer_cells)),
    )


@block
def interactions(stats: Mapping[str, Any]) -> Block | None:
    rows = _rows(stats.get("interactions"))
    if not rows:
        return None
    body = tuple(
        Row(
            (
                Cell(str(i.get("residue"))),
                Cell(str(i.get("type"))),
                _c(i.get("distance"), "Å"),
                Cell(fmt.fraction(i.get("poses"), i.get("of"))),
            )
        )
        for i in rows
    )
    pose = stats.get("interactionsPose")
    return Table(
        "interactions",
        "Interaction fingerprint",
        ("residue", "type", "distance", "poses"),
        body,
        layer=4,
        numeric=(False, False, True, True),
        summary=f"representative pose {pose}" if pose else None,
    )


@block
def sampling(stats: Mapping[str, Any]) -> Block | None:
    rows: list[tuple[str, Cell]] = []
    if "sitePlacement" in stats:
        rows.append(("site placement", Cell(str(stats["sitePlacement"]))))
    if "poseAccuracy" in stats:
        rows.append(("pose accuracy", Cell(str(stats["poseAccuracy"]))))
    pw = stats.get("pairwise")
    if isinstance(pw, Mapping):
        rows.append(("pairwise RMSD median", _c(pw.get("median"), "Å")))
        iqr = pw.get("iqr")
        if isinstance(iqr, list) and len(iqr) == 2:
            rows.append(
                ("pairwise RMSD IQR", Cell(f"{fmt.number(iqr[0])} to {fmt.number(iqr[1], 'Å')}"))
            )
        if "n" in pw:
            rows.append(("pairs", _c(pw.get("n"))))
    if "medoid" in stats:
        rows.append(("medoid", Cell(str(stats["medoid"]))))
    return Card("sampling", "Sampling", tuple(rows), layer=5) if rows else None


@block
def clusters(stats: Mapping[str, Any]) -> Block | None:
    rows = _rows(stats.get("clusters"))
    if not rows:
        return None
    total = sum(int(c.get("size", 0) or 0) for c in rows)
    out = tuple(
        (
            f"cluster {c.get('id')}",
            Cell(
                f"{c.get('size')}/{total} poses", sub=str(c["medoid"]) if c.get("medoid") else None
            ),
        )
        for c in rows
    )
    return Card("clusters", "Clusters", out, layer=5)


@block
def reference(stats: Mapping[str, Any]) -> Block | None:
    ref = stats.get("reference")
    if not isinstance(ref, Mapping):
        return None
    rows: list[tuple[str, Cell]] = []
    redock = ref.get("redocking")
    if isinstance(redock, Mapping):
        sub = " · ".join(str(redock[k]) for k in ("pose", "reference") if redock.get(k))
        rows.append(("redocking RMSD", _c(redock.get("rmsd"), "Å", sub=sub or None)))
    for p in _rows(ref.get("rmsdToCrystal")):
        rows.append((f"RMSD to crystal · {p.get('pose')}", _c(p.get("rmsd"), "Å")))
    return Card("reference", "Reference", tuple(rows), layer=5) if rows else None


@block
def seeds(stats: Mapping[str, Any]) -> Block | None:
    rows = _rows(stats.get("seeds"))
    if not rows:
        return None
    body = tuple(
        Row(
            (
                _c(s.get("seed")),
                Cell(str(s["pose"]) if s.get("pose") is not None else None),
                _c(s.get("cluster")),
                _c(s.get("rmsdToMedoid"), "Å"),
                _c(s.get("confidence")),
            )
        )
        for s in rows
    )
    footer = Row(
        (
            Cell("median"),
            Cell(None),
            Cell(None),
            _c(fmt.median(s.get("rmsdToMedoid") for s in rows), "Å"),
            _c(fmt.median(s.get("confidence") for s in rows)),
        )
    )
    return Table(
        "seeds",
        "Per-seed statistics",
        ("seed", "pose", "cluster", "RMSD to medoid", "confidence"),
        body,
        layer=5,
        numeric=(False, False, True, True, True),
        footer=footer,
    )


@block
def ensemble(stats: Mapping[str, Any]) -> Block | None:
    rows = _rows(stats.get("ensemble"))
    if not rows:
        return None
    body = tuple(
        Row(
            (
                Cell(str(e.get("label", e.get("id"))), state=str(e.get("kind"))),
                Cell(str(e.get("kind"))),
                Cell(str(e["source"]) if e.get("source") else None),
                _c(e.get("rmsdToMedoid"), "Å"),
                _c(e.get("cluster")),
                _c(e.get("pocketPlddt")),
                _c(e.get("iptm")),
            )
        )
        for e in rows
    )
    return Table(
        "ensemble",
        "Ensemble",
        ("structure", "kind", "source", "RMSD to medoid", "cluster", "pocket pLDDT", "ipTM"),
        body,
        layer=5,
        numeric=(False, False, False, True, True, True, True),
        style="ensemble",
    )


@block
def agreement(stats: Mapping[str, Any]) -> Block | None:
    rows = _rows(stats.get("agreement"))
    if not rows:
        return None
    others: list[str] = []
    for r in rows:
        for c in _rows(r.get("cells")):
            vs = str(c.get("vs"))
            if vs not in others:
                others.append(vs)
    body = []
    for r in rows:
        cells = {str(c.get("vs")): c for c in _rows(r.get("cells"))}
        out = [Cell(str(r.get("method")))]
        for vs in others:
            found = cells.get(vs)
            if found is None or vs == r.get("method"):
                out.append(Cell(None))
                continue
            value = found.get("value")
            out.append(
                Cell(
                    fmt.number(value, found.get("unit")),
                    state=_agreement_state(value),
                    sub=str(found["weight"]) if found.get("weight") else None,
                )
            )
        body.append(Row(tuple(out)))
    return Table(
        "agreement",
        "Agreement between methods",
        ("method", *others),
        tuple(body),
        layer=5,
        numeric=(False, *([True] * len(others))),
        style="matrix",
    )


def _agreement_state(value: object) -> str | None:
    """Cell tint as in the prototype matrix: value / 8 Å below 0.25, below 0.6, above."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    t = min(1.0, float(value) / 8)
    return "pass" if t < 0.25 else "warn" if t < 0.6 else "stop"


@block
def metrics(stats: Mapping[str, Any]) -> Block | None:
    rows = _rows(stats.get("metrics"))
    if not rows:
        return None
    ordered = [m for m in rows if not m.get("separate")] + [m for m in rows if m.get("separate")]
    first_sep = next((i for i, m in enumerate(ordered) if m.get("separate")), None)
    body = tuple(
        Row(
            (
                Cell(str(m.get("name"))),
                Cell(str(m["value"]) if m.get("value") is not None else None),
                Cell(str(m["read"]) if m.get("read") else None),
                Cell(str(m["tool"]) if m.get("tool") else None),
            ),
            rule=i == first_sep,
            state="separate" if m.get("separate") else None,
        )
        for i, m in enumerate(ordered)
    )
    return Table(
        "metrics",
        "Confidence metrics",
        ("metric", "value", "read as", "tool"),
        body,
        layer=5,
        numeric=(False, False, False, False),
    )


def controls_table(controls: Sequence[Mapping[str, Any]]) -> Table | None:
    rows = [c for c in controls if isinstance(c, Mapping)]
    if not rows:
        return None
    state = {"sound": "pass", "incomplete": "warn", "missing": "skip"}
    body = tuple(
        Row(
            (
                Cell(str(c.get("name"))),
                Cell(str(c.get("status")), state=state.get(str(c.get("status")))),
                Cell(str(c["note"]) if c.get("note") else None),
            )
        )
        for c in rows
    )
    return Table("controls", "Controls", ("control", "status", "result"), body, layer=5)
