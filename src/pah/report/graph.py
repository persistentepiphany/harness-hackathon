"""Provenance document graph: sources, files, tools, checks and the verdict, with checksums."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pah.core.engine import RunRecord
from pah.core.models import provenance_id

KIND_ORDER = ("source", "file", "tool", "check", "verdict")
GATE_COLOURS = {"pass": "#009E73", "warn": "#E69F00", "stop": "#D55E00", "skip": "#999999"}
KIND_COLOURS = {"source": "#56B4E9", "file": "#CC79A7", "tool": "#F0E442", "verdict": "#0072B2"}


@dataclass
class ProvenanceGraph:
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: list[tuple[str, str, str]] = field(default_factory=list)

    def node(self, nid: str, kind: str, label: str, **attrs: Any) -> str:
        self.nodes.setdefault(nid, {"id": nid, "kind": kind, "label": label, **attrs})
        return nid

    def edge(self, a: str, b: str, relation: str) -> None:
        if (a, b, relation) not in self.edges:
            self.edges.append((a, b, relation))

    def to_json(self) -> dict[str, Any]:
        return {
            "nodes": list(self.nodes.values()),
            "edges": [{"source": a, "target": b, "relation": r} for a, b, r in self.edges],
        }


def build_graph(record: RunRecord) -> ProvenanceGraph:
    g = ProvenanceGraph()
    verdict = record.verdict.outcome.value if record.verdict else "none"
    v = g.node("verdict", "verdict", f"verdict: {verdict}", outcome=verdict, claim=record.claim)
    for p in record.provenance:
        pid = provenance_id(p)
        g.node(
            pid,
            "source",
            f"{p.source_id} {p.accession}",
            release=p.release,
            sha256=p.sha256,
            url=p.url,
        )
    for a in record.artifacts:
        fid = f"file:{a.path}"
        g.node(fid, "file", Path(a.path).name, sha256=a.sha256, artifact_kind=a.kind.value)
        for pid in a.derived_from:
            if pid in g.nodes:
                g.edge(pid, fid, "produced")
    for f in record.findings:
        cid = f"check:{f.check_id}"
        g.node(cid, "check", f.check_id, gate=f.gate.value, layer=int(f.layer))
        for pid in record.usage.get(f.check_id, ()):
            if pid in g.nodes:
                g.edge(pid, cid, "used")
        if f.tool:
            tid = f"tool:{f.tool.name}"
            g.node(
                tid, "tool", f"{f.tool.name} {f.tool.version or ''}".strip(), version=f.tool.version
            )
            g.edge(tid, cid, "ran")
        g.edge(cid, v, "decided")
    return g


def _mermaid_id(index: int) -> str:
    return f"n{index}"


def to_mermaid(g: ProvenanceGraph, title: str) -> str:
    ids = {nid: _mermaid_id(i) for i, nid in enumerate(g.nodes)}
    lines = [
        "flowchart LR",
        f"    accTitle: {title}",
        "    accDescr: Source records and files feed the checks that read them; each check "
        "contributes its gate to the verdict.",
    ]
    for nid, n in g.nodes.items():
        label = str(n["label"]).replace('"', "'")
        if n["kind"] == "check":
            label = f"{label}<br/>{n['gate']}"
        lines.append(f'    {ids[nid]}["{label}"]')
    for a, b, rel in g.edges:
        lines.append(f"    {ids[a]} -->|{rel}| {ids[b]}")
    lines += [f"    classDef {k} fill:{c},stroke:#333,color:#111" for k, c in KIND_COLOURS.items()]
    lines += [f"    classDef {k} fill:{c},stroke:#333,color:#111" for k, c in GATE_COLOURS.items()]
    for nid, n in g.nodes.items():
        cls = n["gate"] if n["kind"] == "check" else n["kind"]
        lines.append(f"    class {ids[nid]} {cls}")
    return "\n".join(lines) + "\n"


def to_svg(g: ProvenanceGraph, path: Path) -> None:
    """Layered drawing: one column per node kind, edges as straight lines."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    columns = {k: [n for n in g.nodes.values() if n["kind"] == k] for k in KIND_ORDER}
    rows = max((len(v) for v in columns.values()), default=1)
    fig, ax = plt.subplots(figsize=(13, max(3.0, 0.42 * rows + 1)))
    fig.subplots_adjust(left=0.01, right=0.99, top=0.98, bottom=0.01)
    pos: dict[str, tuple[float, float]] = {}
    for x, kind in enumerate(KIND_ORDER):
        nodes = columns[kind]
        for i, n in enumerate(nodes):
            y = (len(nodes) - 1) / 2 - i
            pos[n["id"]] = (x * 3.2, y)
    for a, b, _ in g.edges:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        ax.plot([x1 + 1.3, x2 - 1.3], [y1, y2], color="#888888", lw=0.6, zorder=1)
    for nid, (px, py) in pos.items():
        n = g.nodes[nid]
        colour = GATE_COLOURS.get(n.get("gate", ""), KIND_COLOURS.get(n["kind"], "#dddddd"))
        label = str(n["label"])
        if n["kind"] == "check":
            label = f"{label} [{n['gate']}]"
        ax.text(
            px,
            py,
            label[:44],
            ha="center",
            va="center",
            fontsize=7,
            zorder=2,
            bbox={"boxstyle": "round,pad=0.25", "fc": colour, "ec": "#333333", "lw": 0.5},
        )
    for x, kind in enumerate(KIND_ORDER):
        ax.text(x * 3.2, rows / 2 + 0.4, kind, ha="center", fontsize=9, weight="bold")
    ax.set_xlim(-1.8, (len(KIND_ORDER) - 1) * 3.2 + 1.8)
    ax.set_ylim(-rows / 2 - 0.2, rows / 2 + 0.8)
    ax.axis("off")
    fig.savefig(path, format=path.suffix.lstrip(".") or "svg")
    plt.close(fig)


def write_graph(record: RunRecord, out_dir: Path) -> dict[str, Path]:
    g = build_graph(record)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": out_dir / "graph.json",
        "mmd": out_dir / "graph.mmd",
        "svg": out_dir / "graph.svg",
    }
    paths["json"].write_text(json.dumps(g.to_json(), indent=2))
    paths["mmd"].write_text(to_mermaid(g, f"Provenance graph for run {record.run_id}"))
    to_svg(g, paths["svg"])
    return paths
