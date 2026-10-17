"""Self-contained HTML reports in the style of the web UI's report and document views.

`render_html` reads only the `UiRunRecord` (pah.api.adapter) and the figure list, so the HTML
shows exactly the values the UI shows. Text is escaped; there is no JavaScript. The print
stylesheet lays the page out as the A4 document view, so printing to PDF gives the document.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from html import escape
from itertools import count
from typing import Any
from urllib.parse import quote

from pah import __version__
from pah.core.models import Artifact
from pah.report import fmt
from pah.report.model import BatchReport, FigureEntry
from pah.report.view import Block, Card, Cell, Table, controls_table, stats_blocks

FONTS = (
    "https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600"
    "&family=Geist+Mono:wght@400;500&display=swap"
)
OUTCOME_LABEL = {
    "supported": "Supported",
    "narrowed": "Narrowed",
    "refused": "Refused",
    "incomplete": "Incomplete",
}
URL = re.compile(r"^/runs/[^/]+/files/(.+)$")
UNIT = re.compile("(\\S+\u2009\\S+)")

CSS = """
:root{--canvas:#F7F7F4;--surface:#FFFFFF;--ink:#1A1A18;--ink2:#55554F;--muted:#8B8B85;
--faint:#B9B9B3;--line:#E6E6E1;--line2:#EFEFEB;--line3:#F3F3EF;--accent:#B07E2C;
--accent-deep:#8E6420;--accent-t:#F6EEDC;--pass:#3B8A58;--pass-t:#E4F1E8;--warn:#C28A1A;
--warn-t:#FAF0D9;--stop:#C4513B;--stop-t:#F9E5E0;--rep:#8B8B85;--rep-t:#EFEFEB;
--cofolding:#B07E2C;--docking:#5B7FA6;--seed:#C9A86A;--model:#8B6FB5;
--sans:Geist,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
--mono:"Geist Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--canvas);color:var(--ink);font-family:var(--sans);
font-size:13px;line-height:1.45;-webkit-font-smoothing:antialiased}
a{color:var(--ink);text-decoration:none}a:hover{color:var(--accent)}
h1,h2,h3{margin:0;font-weight:600}
.mono,.v,td.m{font-family:var(--mono);font-size:11.5px}
.muted{color:var(--muted)}
.na::before{content:"\\2013";color:var(--faint)}
.eyebrow{font-size:11px;font-weight:500;letter-spacing:.06em;text-transform:uppercase;
color:var(--muted)}
.page{max-width:1280px;margin:0 auto;padding:44px 24px 80px;display:flex;flex-direction:column;
gap:28px}
.doc-head{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;
border-bottom:1px solid var(--ink);padding-bottom:12px}
.doc-title{font-size:17px;font-weight:600;letter-spacing:-.01em;margin-top:2px}
.doc-id{text-align:right;color:var(--ink2);font-size:11px;line-height:1.6}
.verdict{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.verdict-label{font-size:22px;font-weight:600;letter-spacing:-.015em;padding:1px 10px 2px;
border-radius:6px;background:var(--rep-t);color:var(--ink2)}
.verdict-label[data-o=supported]{color:var(--pass);background:var(--pass-t)}
.verdict-label[data-o=narrowed]{color:var(--accent-deep);background:var(--warn-t)}
.verdict-label[data-o=refused]{color:var(--stop);background:var(--stop-t)}
.claim{font-size:15px}
.statement{color:var(--ink2);margin-top:8px;line-height:1.6}
.flagged{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:8px}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,max-content));
gap:10px 32px;margin:18px 0 0;font-size:12.5px}
.meta dt{font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);
margin-bottom:3px}
.meta dd{margin:0;max-width:340px;overflow-wrap:anywhere}
.tool{display:inline-flex;align-items:center;gap:6px;margin-right:12px;white-space:nowrap}
.fam{width:7px;height:7px;border-radius:50%;display:inline-block}
.fam[data-f=co-folding]{background:var(--cofolding)}
.fam[data-f=docking]{background:var(--docking);background:transparent;
border:1.5px dashed var(--docking)}
.layout{display:grid;grid-template-columns:230px minmax(0,1fr);gap:40px;align-items:start}
.side{position:sticky;top:24px;display:flex;flex-direction:column;gap:24px}
.nav a{display:block;border-left:2px solid var(--line);padding:8px 0 8px 12px}
.nav a:hover{border-color:var(--faint);color:var(--ink)}
.nav .row{display:flex;justify-content:space-between;align-items:center;gap:8px;
font-weight:500;color:var(--ink2)}
.nav .sub{font-family:var(--mono);font-size:10.5px;letter-spacing:-.02em;color:var(--muted);
margin-top:3px;
line-height:1.5}
.trace{font-family:var(--mono);font-size:11px;color:var(--muted);line-height:1.7;
padding-left:14px}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;flex:none;
border:1.5px solid transparent}
.dot[data-r=pass]{background:var(--pass);border-color:var(--pass)}
.dot[data-r=warn]{background:var(--warn);border-color:var(--warn)}
.dot[data-r=stop],.dot[data-r=fail]{background:var(--stop);border-color:var(--stop)}
.dot[data-r=skip],.dot[data-r=reported]{border-color:var(--muted)}
.dot[data-r=pending]{border-color:var(--faint)}
.dot[data-r=not_run]{border-color:var(--line)}
.dot[data-r=medoid]{background:var(--accent);border-color:var(--accent)}
.dot[data-r=seed]{background:var(--seed);border-color:var(--seed)}
.dot[data-r=docking]{border:1.5px dashed var(--docking)}
.dot[data-r=crystal]{background:var(--ink);border-color:var(--ink)}
.dot[data-r=model]{background:var(--model);border-color:var(--model)}
.chip{display:inline-block;font-size:10.5px;font-weight:600;letter-spacing:.04em;
text-transform:uppercase;padding:1px 7px;border-radius:4px;white-space:nowrap;
color:var(--rep);background:var(--rep-t)}
.chip[data-r=pass],.chip[data-o=supported]{color:var(--pass);background:var(--pass-t)}
.chip[data-r=warn],.chip[data-o=narrowed]{color:var(--accent-deep);background:var(--warn-t)}
.chip[data-r=stop],.chip[data-o=refused]{color:var(--stop);background:var(--stop-t)}
.chip[data-r=pending],.chip[data-r=not_run]{color:var(--faint);background:transparent;
border:1px solid var(--line)}
.chip.big{font-size:11.5px;padding:3px 9px}
.cnt span{white-space:nowrap}.cnt .z{color:var(--faint)}
.keys{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:16px}
.key{border-top:1px solid var(--ink);padding-top:8px}
.key .n{font-family:var(--mono);font-size:20px;font-weight:500;letter-spacing:-.01em}
.key .n.z{color:var(--faint)}
.key[data-r=warn] .n{color:var(--accent-deep)}.key[data-r=stop] .n{color:var(--stop)}
.key .l{font-size:11px;color:var(--muted);margin-top:2px}
.keys{margin-bottom:24px}
.print-only,.strip.print-only{display:none}
.content{display:flex;flex-direction:column;gap:40px;min-width:0}
.strip{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border-top:1px solid var(--line);
border-bottom:1px solid var(--line)}
.strip .cell{padding:10px 12px;border-left:1px solid var(--line3)}
.strip .cell:first-child{border-left:0;padding-left:0}
.strip .name{display:flex;align-items:center;gap:7px;font-weight:500;font-size:12.5px}
.strip .sub{font-family:var(--mono);font-size:10.5px;color:var(--muted);margin-top:4px;
line-height:1.6}
.section-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;
margin-bottom:6px}
.section-head h2{font-size:14px}
.lnum{font-family:var(--mono);font-size:11px;color:var(--muted);margin-right:8px;font-weight:500}
.question{color:var(--muted);font-size:12.5px;margin-bottom:10px}
.layer{display:flex;flex-direction:column;gap:18px}
.layer-intro{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;
align-items:baseline}
.kvgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:0 28px}
.kv{display:flex;justify-content:space-between;gap:10px;padding:4px 0;
border-bottom:1px solid var(--line3);font-size:12px}
.kv .k{color:var(--ink2)}.kv .v{text-align:right;overflow-wrap:anywhere}
.kv .s{display:block;color:var(--muted);font-size:10.5px}
table{width:100%;border-collapse:collapse}
th{font-family:var(--mono);font-size:10.5px;color:var(--muted);font-weight:400;text-align:left;
padding:7px 10px 7px 0;border-bottom:1px solid var(--line2);vertical-align:bottom}
th.num,td.num{text-align:right}
.checks{border-top:1px solid var(--line);table-layout:fixed}
.checks td{padding:10px 14px 10px 0;border-bottom:1px solid var(--line2);vertical-align:baseline}
.checks td:last-child{padding-right:0;text-align:right}
.checks .name{font-size:13px}
.checks .tool{display:block;font-family:var(--mono);font-size:10.5px;color:var(--muted);
margin-top:2px}
.checks .ev{font-family:var(--mono);font-size:11.5px;color:var(--ink2);overflow-wrap:anywhere}
.checks .cmp{font-family:var(--mono);font-size:11.5px;overflow-wrap:anywhere}
.checks .cmp .o{display:block;font-size:10px;color:var(--muted);white-space:normal}
.checks .id{font-family:var(--mono);font-size:10.5px;color:var(--muted);overflow-wrap:anywhere}
.checks tr[data-state=skip] .name,.checks tr[data-state=pending] .name{color:var(--ink2)}
.data{border-top:1px solid var(--line)}
.data td{font-family:var(--mono);font-size:11.5px;padding:6px 10px 6px 0;
border-bottom:1px solid var(--line3);color:var(--ink2);overflow-wrap:anywhere}
.data td:first-child{color:var(--ink)}
.data tfoot td{font-weight:500;color:var(--ink);border-bottom:0;padding-top:8px}
.data tr.rule td{border-top:1px solid var(--accent)}
.data tr[data-state=separate] td{color:var(--ink2)}
.block-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;
margin-bottom:8px}
.block-head h3{font-size:13px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px}
.u{white-space:nowrap}.kv .k{white-space:nowrap}
.card{border-top:1px solid var(--ink);padding-top:10px}
.card .eyebrow{margin-bottom:8px}
.card .kv{border:0;padding:3px 0}
.pb{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:4px 16px;
border-top:1px solid var(--line);padding-top:8px}
.pb-item{display:flex;justify-content:space-between;align-items:baseline;gap:8px;
padding:4px 0;font-family:var(--mono);
font-size:11px}
.pb-item .t{display:flex;align-items:center;gap:7px;min-width:0;color:var(--ink2);
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pb-item .dot{width:6px;height:6px}.pb-item .nm{overflow:hidden;text-overflow:ellipsis}
.pb-item .muted{white-space:nowrap}
.matrix{display:grid;gap:4px;font-family:var(--mono);font-size:11.5px;max-width:640px}
.matrix .h{text-align:center;color:var(--muted);padding-bottom:2px}
.matrix .m{color:var(--ink2);display:flex;align-items:center}
.mcell{border-radius:4px;padding:10px 6px;text-align:center;background:var(--canvas);
color:var(--faint)}
.mcell .val{font-size:13px;font-weight:500}.mcell .w{font-size:10px;opacity:.8;margin-top:1px}
.mcell[data-r=pass]{background:var(--pass-t);color:var(--pass)}
.mcell[data-r=warn]{background:var(--warn-t);color:var(--accent-deep)}
.mcell[data-r=stop]{background:var(--stop-t);color:var(--stop)}
.figs{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px}
.fig{margin:0}
.fig img{max-width:100%;max-height:340px;width:auto;height:auto;display:block;
background:var(--surface);
border:1px solid var(--line);border-radius:8px;padding:8px}
figcaption{font-size:11px;color:var(--muted);margin-top:8px;line-height:1.5}
figcaption a{color:var(--muted);text-decoration:underline;text-decoration-color:var(--line)}
.renders{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}
.render{margin:0}
.render img{width:100%;aspect-ratio:4/3;object-fit:contain;display:block;
background:var(--surface);border:1px solid var(--line);border-radius:8px}
.prov td,.files td{font-family:var(--mono);font-size:11px;color:var(--ink2);padding:5px 10px 5px 0;
border-bottom:1px solid var(--line3);overflow-wrap:anywhere}
.prov td:first-child,.files td:first-child{color:var(--ink)}
.foot{font-family:var(--mono);font-size:11px;color:var(--muted);border-top:1px solid var(--line);
padding-top:14px;line-height:1.7}
.errors{font-family:var(--mono);font-size:11px;color:var(--stop)}
@media (max-width:900px){.layout{grid-template-columns:minmax(0,1fr)}.side{display:none}
.keys{grid-template-columns:repeat(4,minmax(0,1fr))}}
@page{size:A4;margin:16mm 15mm 18mm}
@media print{
html,body{background:#fff;font-size:9.5pt}
*{-webkit-print-color-adjust:exact;print-color-adjust:exact}
.page{max-width:none;padding:0;gap:16px}
.layout{display:block}.side{display:none}
.content{display:block}.content>*+*{margin-top:22px}
.verdict-label{font-size:15pt}.claim{font-size:11pt}.doc-title{font-size:15pt}
.eyebrow,.meta dt{font-size:7.5pt}
.mono,.v,td.m,.data td,.checks .ev,.checks .cmp,.prov td,.files td,.pb-item,.matrix{font-size:8pt}
.checks td{padding:5px 8px 5px 0}.checks .name{font-size:9pt}.checks .id{font-size:7.5pt}
.meta{gap:6px 22px;font-size:9pt}
section.layer.page{break-before:page}
.section-head,.block-head,.layer-intro{break-after:avoid}
.keys{grid-template-columns:repeat(7,minmax(0,1fr));gap:10px}
.strip .name{font-size:8.5pt}.strip .sub{font-size:7pt}
.print-only{display:block}.strip.print-only{display:grid}
.key .n{font-size:14pt}.key .l{font-size:7.5pt}
table,figure,.card,.pb,.matrix,.kvgrid,.strip,tr,.block{break-inside:avoid}
thead{display:table-header-group}
.fig img{max-height:80mm;width:auto}
.figs{grid-template-columns:repeat(2,minmax(0,1fr))}
.renders{grid-template-columns:repeat(3,minmax(0,1fr))}
a{color:inherit}
}
"""


def e(value: object) -> str:
    return escape(str(value), quote=True)


def na() -> str:
    return '<span class="na" title="not reported"></span>'


def text(value: str | None) -> str:
    """Escaped value; a missing one renders as the muted dash, a value with a unit stays on
    one line."""
    if value is None or value == "":
        return na()
    return UNIT.sub(r'<span class="u">\1</span>', e(value))


def _href(assets_rel: str, rel: str) -> str:
    return e(assets_rel + quote(rel, safe="/"))


def _rel(url: str) -> str:
    m = URL.match(url)
    return m.group(1) if m else url


def dot(state: str | None, label: str | None = None) -> str:
    title = f' title="{e(label)}"' if label else ""
    return f'<span class="dot" data-r="{e(state or "")}"{title}></span>'


def chip(result: str, *, big: bool = False, attr: str = "r", label: str | None = None) -> str:
    cls = "chip big" if big else "chip"
    shown = (label if label is not None else result).replace("_", " ")
    return f'<span class="{cls}" data-{attr}="{e(result)}">{e(shown)}</span>'


def counts_html(counts: Mapping[str, int]) -> str:
    parts = []
    for g, n in fmt.counts(counts):
        z = ' class="z"' if n == 0 else ""
        parts.append(f"<span{z}>{e(g)} {n}</span>")
    return '<span class="cnt">' + " · ".join(parts) + "</span>"


def _layer_state(layer: Mapping[str, Any]) -> str:
    from pah.api.adapter import worst

    if layer.get("status") != "done":
        return str(layer.get("status"))
    return worst(c["result"] for c in layer.get("checks", [])) or "skip"


# ---- header -------------------------------------------------------------------------------


def _header(ui: Mapping[str, Any], title: str) -> str:
    v = ui.get("verdict") or {}
    outcome = str(v.get("outcome") or "pending")
    label = OUTCOME_LABEL.get(outcome, "Running")
    created = fmt.when(ui.get("createdAt"))
    flagged = []
    for key, state in (("stops", "stop"), ("warnings", "warn")):
        for cid in v.get(key, []):
            flagged.append(f'<span class="mono">{chip(state)} {e(cid)}</span>')
    inc = v.get("incomplete") or []
    if inc:
        flagged.append(f'<span class="mono">{chip("skip")} {len(inc)} not verified</span>')
    return f"""<header class="head">
<div class="doc-head"><div><div class="eyebrow">Prediction assurance · run report</div>
<h1 class="doc-title">{e(title)}</h1></div>
<div class="doc-id mono">{e(ui.get("id", ""))}<br>{text(created)}</div></div>
<div style="margin-top:22px" class="verdict" data-testid="verdict" data-state="{e(outcome)}">
<span class="verdict-label" data-o="{e(outcome)}">{e(label)}</span>
<span class="claim">“{e(v.get("claim") or ui.get("claim", ""))}”</span></div>
<div class="statement mono" data-testid="statement">{text(v.get("statement"))}</div>
{f'<div class="flagged">{"".join(flagged)}</div>' if flagged else ""}
{_meta(ui)}
</header>"""


def _meta(ui: Mapping[str, Any]) -> str:
    inputs = ui.get("inputs") or {}
    tools = "".join(
        f'<span class="tool"><span class="fam" data-f="{e(t.get("family", ""))}"></span>'
        f"{e(t['name'])}"
        + (f' <span class="mono muted">{e(t["version"])}</span>' if t.get("version") else "")
        + "</span>"
        for t in ui.get("tools", [])
    )
    seeds = inputs.get("seeds")
    items = [
        ("Task", e(ui.get("taskName") or ui.get("task", ""))),
        ("Tools", tools or na()),
        ("Target", f'<span class="mono">{text(inputs.get("target"))}</span>'),
        ("Ligand", f'<span class="mono">{text(inputs.get("ligand"))}</span>'),
        ("Reference", f'<span class="mono">{text(inputs.get("reference"))}</span>'),
        ("pH", f'<span class="mono">{text(fmt.number(inputs.get("ph")))}</span>'),
        ("Seeds", f'<span class="mono">{text(fmt.number(seeds))}</span>'),
        ("Run", f'<span class="mono">{e(ui.get("id", ""))}</span>'),
        ("Created", f'<span class="mono">{text(fmt.when(ui.get("createdAt")))}</span>'),
    ]
    if inputs.get("partner"):
        items.insert(3, ("Partner", f'<span class="mono">{e(inputs["partner"])}</span>'))
    body = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in items)
    return f'<dl class="meta" data-testid="meta">{body}</dl>'


def _sub_line(layer: Mapping[str, Any]) -> str:
    if layer.get("status") == "not_run":
        return "not run"
    d = fmt.duration(layer.get("durationMs"))
    return counts_html(layer.get("counts", {})) + (f"<br>{e(d)}" if d else "")


def _strip(ui: Mapping[str, Any]) -> str:
    cells = []
    for layer in ui.get("layers", []):
        state = _layer_state(layer)
        cells.append(
            f'<div class="cell" data-testid="layer-cell" data-layer="{layer["i"]}" '
            f'data-state="{e(state)}"><div class="name">{dot(state)}'
            f'<span class="lnum">L{layer["i"]}</span>{e(layer["name"])}</div>'
            f'<div class="sub">{_sub_line(layer)}</div></div>'
        )
    return f'<div class="strip print-only" data-testid="layer-strip">{"".join(cells)}</div>'


def _keys(ui: Mapping[str, Any]) -> str:
    """Key numbers row: checks, gate counts, sources and time."""
    total = _total(ui)
    checks = sum(total.values())
    ms = sum(layer.get("durationMs", 0) for layer in ui.get("layers", []))
    items: list[tuple[str | None, str, str]] = [
        (str(checks), "checks", ""),
        *((str(total.get(g, 0)), g, g) for g in fmt.GATES),
        (str(len(ui.get("sources") or [])), "source records", ""),
        (fmt.duration(ms) if ms else None, "layer time", ""),
    ]
    cells = "".join(
        f'<div class="key" data-r="{e(r)}"><div class="n{" z" if n == "0" else ""}">{text(n)}'
        f'</div><div class="l">{e(label)}</div></div>'
        for n, label, r in items
    )
    return f'<div class="keys" data-testid="key-numbers">{cells}</div>'


def _sidebar(ui: Mapping[str, Any]) -> str:
    links = []
    for layer in ui.get("layers", []):
        state = _layer_state(layer)
        links.append(
            f'<a href="#layer-{layer["i"]}" data-testid="layer-nav" data-layer="{layer["i"]}" '
            f'data-state="{e(state)}"><div class="row"><span>{e(layer["name"])}</span>'
            f'{dot(state)}</div><div class="sub">{_sub_line(layer)}</div></a>'
        )
    checks = [c for layer in ui.get("layers", []) for c in layer.get("checks", [])]
    total_ms = sum(layer.get("durationMs", 0) for layer in ui.get("layers", []))
    lines = [f"{len(checks)} checks · {fmt.duration(total_ms) or ''}"]
    lines += [f"{t['name']} {t.get('version', '')}".strip() for t in ui.get("tools", [])]
    record = ui.get("record") or {}
    lines += [f"{k} {v}" for k, v in sorted((record.get("toolVersions") or {}).items())]
    if record.get("pahVersion"):
        lines.append(f"pah {record['pahVersion']}")
    trace = "<br>".join(e(x) for x in lines)
    return (
        f'<aside class="side" data-print="hide"><nav class="nav"><div class="eyebrow" '
        f'style="margin-bottom:8px">Layers</div>{"".join(links)}</nav>'
        f'<div class="trace">{trace}</div></aside>'
    )


# ---- blocks -------------------------------------------------------------------------------


def _cell(c: Cell, numeric: bool = False) -> str:
    cls = ' class="num"' if numeric else ""
    title = f' title="{e(c.title)}"' if c.title else ""
    body = text(c.text)
    if c.sub:
        body += f'<span class="s muted"> · {e(c.sub)}</span>'
    return f"<td{cls}{title}>{body}</td>"


def _state_cell(c: Cell) -> str:
    return f"<td>{chip(c.state or '', label=c.text or '')}</td>"


def _table(t: Table) -> str:
    num = t.numeric or tuple(False for _ in t.columns)
    head = "".join(
        f'<th class="num">{e(c)}</th>' if n else f"<th>{e(c)}</th>"
        for c, n in zip(t.columns, num, strict=False)
    )
    rows = []
    for r in t.rows:
        cls = ' class="rule"' if r.rule else ""
        state = f' data-state="{e(r.state)}"' if r.state else ""
        cells = []
        for i, (c, n) in enumerate(zip(r.cells, num, strict=False)):
            if i == 0 and t.style == "ensemble":
                cells.append(f"<td>{dot(c.state)} {text(c.text)}</td>")
            else:
                cells.append(_state_cell(c) if c.state and i else _cell(c, n))
        rows.append(f'<tr data-testid="{e(t.id)}-row"{cls}{state}>{"".join(cells)}</tr>')
    foot = ""
    if t.footer:
        tail = "".join(_cell(c, n) for c, n in zip(t.footer.cells, num, strict=False))
        foot = f"<tfoot><tr>{tail}</tr></tfoot>"
    return (
        f'<table class="data"><thead><tr>{head}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody>{foot}</table>"
    )


def _grid(t: Table) -> str:
    items = []
    for r in t.rows:
        name, result, value = r.cells
        items.append(
            f'<div class="pb-item" data-testid="posebusters-test" data-state="{e(r.state or "")}">'
            f'<span class="t">{dot(result.state)}<span class="nm">{text(name.text)}</span></span>'
            f'<span class="muted">{text(value.text)}</span></div>'
        )
    return f'<div class="pb">{"".join(items)}</div>'


def _matrix(t: Table) -> str:
    n = len(t.columns) - 1
    parts = ["<div></div>"] + [f'<div class="h">{e(c)}</div>' for c in t.columns[1:]]
    for r in t.rows:
        parts.append(f'<div class="m">{text(r.cells[0].text)}</div>')
        for c in r.cells[1:]:
            sub = f'<div class="w">{e(c.sub)}</div>' if c.sub else ""
            parts.append(
                f'<div class="mcell" data-r="{e(c.state or "")}"><div class="val">{text(c.text)}'
                f"</div>{sub}</div>"
            )
    style = f"grid-template-columns:110px repeat({n},minmax(0,120px))"
    return f'<div class="matrix" style="{style}">{"".join(parts)}</div>'


def _block(b: Block) -> str:
    if isinstance(b, Card):
        return _card(b)
    summary = f'<span class="mono muted">{e(b.summary)}</span>' if b.summary else ""
    body = {"grid": _grid, "matrix": _matrix}.get(b.style, _table)(b)
    caption = f"<figcaption>{e(b.caption)}</figcaption>" if b.caption else ""
    return (
        f'<div class="block" data-testid="stats-{e(b.id)}"><div class="block-head">'
        f"<h3>{e(b.title)}</h3>{summary}</div>{body}{caption}</div>"
    )


def _card(c: Card) -> str:
    rows = "".join(
        f'<div class="kv"><span class="k">{e(k)}</span><span class="v">{text(v.text)}'
        + (f'<span class="s">{e(v.sub)}</span>' if v.sub else "")
        + "</span></div>"
        for k, v in c.rows
    )
    return (
        f'<div class="card" data-testid="stats-{e(c.id)}"><div class="eyebrow">{e(c.title)}</div>'
        f"{rows}</div>"
    )


def _blocks(blocks: Sequence[Block]) -> str:
    """Cards side by side in one grid, tables full width, in builder order."""
    out: list[str] = []
    cards: list[str] = []
    for b in blocks:
        if isinstance(b, Card):
            cards.append(_card(b))
            continue
        if cards:
            out.append(f'<div class="cards">{"".join(cards)}</div>')
            cards = []
        out.append(_block(b))
    if cards:
        out.append(f'<div class="cards">{"".join(cards)}</div>')
    return "".join(out)


# ---- checks, figures, provenance ----------------------------------------------------------


def _evidence(c: Mapping[str, Any]) -> str:
    if c.get("result") == "pending":
        return na()
    reason = c.get("skipReason")
    if reason == "unknown_check":
        return '<span class="muted">not implemented</span>'
    ev = text(c.get("evidence") or c.get("message"))
    if reason:
        ev += f'<span class="muted"> · {e(str(reason).replace("_", " "))}</span>'
    return ev


def _checks(checks: Sequence[Mapping[str, Any]]) -> str:
    rows = []
    for c in checks:
        cmp = fmt.compare(c)
        t = c.get("threshold") or {}
        origin = (
            f'<span class="o">{e(t.get("origin", ""))} · {e(t.get("evidenceLevel", ""))}</span>'
            if t
            else ""
        )
        tool = f'<span class="tool">{e(c["tool"])}</span>' if c.get("tool") else ""
        ms = fmt.duration(c.get("ms"))
        ident = e(c["id"]).replace(".", ".<wbr>") + (
            f' · <span class="u">{e(ms)}</span>' if ms else ""
        )
        rows.append(
            f'<tr data-testid="check-row" data-check="{e(c["id"])}" data-state="{e(c["result"])}">'
            f"<td>{dot(c['result'])}</td>"
            f'<td class="name">{e(c["name"])}{tool}</td>'
            f'<td class="cmp">{text(cmp)}{origin}</td>'
            f'<td class="ev">{_evidence(c)}</td>'
            f'<td class="id">{ident}</td>'
            f"<td>{chip(str(c['result']))}</td></tr>"
        )
    head = (
        "<thead><tr><th></th><th>check</th><th>measured cmp threshold</th><th>evidence</th>"
        '<th>id · time</th><th class="num">result</th></tr></thead>'
    )
    cols = (
        '<colgroup><col style="width:16px"><col style="width:25%"><col style="width:17%">'
        '<col><col style="width:19%"><col style="width:68px"></colgroup>'
    )
    return f'<table class="checks">{cols}{head}<tbody>{"".join(rows)}</tbody></table>'


def _figure(f: FigureEntry, n: int, assets_rel: str) -> str:
    links = []
    if f.data_path:
        links.append(f'<a href="{_href(assets_rel, f.data_path)}">data</a>')
    if f.session_path:
        links.append(f'<a href="{_href(assets_rel, f.session_path)}">PyMOL session</a>')
    extra = (" · " + " · ".join(links)) if links else ""
    return (
        f'<figure class="fig" data-testid="figure" data-figure="{e(f.id)}">'
        f'<img src="{_href(assets_rel, f.path)}" alt="{e(f.alt)}">'
        f"<figcaption>Fig. {n} · {e(f.caption)}{extra}</figcaption></figure>"
    )


def _figures(figs: Sequence[FigureEntry], numbers: Iterable[int], assets_rel: str) -> str:
    if not figs:
        return ""
    body = "".join(_figure(f, n, assets_rel) for f, n in zip(figs, numbers, strict=False))
    return f'<div class="figs">{body}</div>'


def _renders(ui: Mapping[str, Any], figures: Sequence[FigureEntry], assets_rel: str) -> str:
    renders = ui.get("renders") or []
    if not renders:
        return ""
    captions = {f.path: f.caption for f in figures if f.kind == "render"}
    items = []
    for r in renders:
        png, pse = _rel(str(r["png"])), _rel(str(r["pse"]))
        caption = captions.get(png) or f"{r['structure']} · {r['view']}"
        items.append(
            f'<figure class="render" data-testid="render" data-structure="{e(r["structure"])}">'
            f'<img src="{_href(assets_rel, png)}" alt="PyMOL render of {e(r["structure"])}, '
            f'{e(r["view"])} view"><figcaption>{e(caption)} · '
            f'<a href="{_href(assets_rel, pse)}">PyMOL session</a></figcaption></figure>'
        )
    return (
        '<section data-testid="renders"><div class="section-head"><h2>Structures</h2>'
        f'<span class="mono muted">{len(renders)} PyMOL renders</span></div>'
        f'<div class="renders">{"".join(items)}</div></section>'
    )


def _layer(
    layer: Mapping[str, Any],
    stats: Mapping[str, Any],
    figs: Sequence[FigureEntry],
    numbers: Iterable[int],
    assets_rel: str,
    first: bool = False,
) -> str:
    """One layer section. In print it starts a page when it is the first layer that ran
    or carries stats blocks or figures."""
    i = layer["i"]
    status = str(layer.get("status"))
    ran = status != "not_run"
    head = (
        '<div class="layer-intro"><div><div class="section-head"><h2>'
        f'<span class="lnum">L{i}</span>'
        f'{e(layer["name"])}</h2></div><div class="question">{e(layer.get("question", ""))}'
        f'</div></div><div class="mono muted">{_sub_line(layer)}</div></div>'
    )
    parts = [head]
    blocks = stats_blocks(stats, i) if ran else []
    if ran:
        kv = "".join(
            f'<div class="kv"><span class="k">{e(k)}</span><span class="v">{e(v)}</span></div>'
            for k, v in layer.get("figures") or []
        )
        if kv:
            parts.append(f'<div class="kvgrid" data-testid="key-figures">{kv}</div>')
        parts.append(_blocks(blocks))
        parts.append(_figures(figs, numbers, assets_rel))
        if layer.get("checks"):
            parts.append(_checks(layer["checks"]))
    cls = "layer ran" + (" page" if first or blocks or figs else "") if ran else "layer"
    return (
        f'<section class="{cls}" id="layer-{i}" data-testid="layer" data-layer="{i}" '
        f'data-state="{e(status)}">{"".join(p for p in parts if p)}</section>'
    )


def _provenance(sources: Sequence[Mapping[str, Any]]) -> str:
    if not sources:
        return ""
    cached = sum(1 for s in sources if s.get("cached") is True)
    network = sum(1 for s in sources if s.get("cached") is False)
    rows = []
    for s in sources:
        sha = str(s.get("sha256") or "")
        cache = {True: "hit", False: "miss"}.get(bool(s["cached"])) if "cached" in s else None
        acc = e(s.get("accession", ""))
        if s.get("url"):
            acc = f'<a href="{e(s["url"])}">{acc}</a>'
        rows.append(
            f'<tr data-testid="source-row" data-source="{e(s.get("source", ""))}">'
            f"<td>{e(s.get('source', ''))}</td><td>{acc}</td><td>{text(s.get('release'))}</td>"
            f'<td title="{e(sha)}">{text(fmt.sha12(sha))}</td>'
            f"<td>{text(fmt.when(s.get('retrievedAt')))}</td>"
            f'<td class="num">{text(fmt.number(s.get("sizeBytes")))}</td>'
            f"<td>{text(cache)}</td></tr>"
        )
    head = (
        "<thead><tr><th>source</th><th>accession</th><th>release</th><th>sha256</th>"
        '<th>retrieved</th><th class="num">bytes</th><th>cache</th></tr></thead>'
    )
    summary = f"{len(sources)} objects · {cached} cached · {network} network"
    return (
        f'<section data-testid="provenance"><div class="section-head"><h2>Provenance</h2>'
        f'<span class="mono muted">{e(summary)}</span></div>'
        f'<table class="prov">{head}<tbody>{"".join(rows)}</tbody></table></section>'
    )


def _thresholds(ui: Mapping[str, Any]) -> str:
    rows = []
    for layer in ui.get("layers", []):
        for c in layer.get("checks", []):
            for t in c.get("thresholds") or []:
                rows.append(
                    f"<tr><td>{e(c['id'])}</td><td>{e(t['name'])}</td>"
                    f"<td>{e(t['comparator'])} {e(fmt.number(t['value']))}</td>"
                    f"<td>{e(t['origin'])}</td><td>{e(t['evidenceLevel'])}</td></tr>"
                )
    if not rows:
        return ""
    head = (
        "<thead><tr><th>check</th><th>threshold</th><th>value</th><th>origin</th>"
        "<th>evidence level</th></tr></thead>"
    )
    return (
        '<section data-testid="thresholds"><div class="section-head"><h2>Thresholds</h2>'
        f'<span class="mono muted">{len(rows)} thresholds</span></div>'
        f'<table class="prov">{head}<tbody>{"".join(rows)}</tbody></table></section>'
    )


def _files(files: Sequence[Artifact], assets_rel: str) -> str:
    if not files:
        return ""
    rows = []
    for a in files:
        path = e(a.path)
        if not a.path.startswith("/"):
            path = f'<a href="{_href(assets_rel, a.path)}">{path}</a>'
        rows.append(
            f'<tr data-testid="file-row"><td>{path}</td><td>{e(a.kind.value)}</td>'
            f'<td class="num">{a.size_bytes}</td>'
            f'<td title="{e(a.sha256)}">{e(a.sha256[:12])}</td></tr>'
        )
    head = (
        '<thead><tr><th>path</th><th>kind</th><th class="num">bytes</th>'
        "<th>sha256</th></tr></thead>"
    )
    return (
        '<section data-testid="files"><div class="section-head"><h2>Files</h2>'
        f'<span class="mono muted">{len(files)} files</span></div>'
        f'<table class="files">{head}<tbody>{"".join(rows)}</tbody></table></section>'
    )


def _doc(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{e(FONTS)}">
<style>{CSS}</style></head>
<body>{body}</body></html>
"""


def render_html(
    ui: Mapping[str, Any],
    *,
    figures: Sequence[FigureEntry] = (),
    assets_rel: str = "",
    files: Sequence[Artifact] = (),
    limitations: Sequence[str] = (),
    errors: Sequence[str] = (),
) -> str:
    """One self-contained page from a `UiRunRecord`. `assets_rel` prefixes run-relative paths."""
    v = ui.get("verdict") or {}
    title = f"Run report · {ui.get('taskName') or ui.get('task', '')}"
    stats = ui.get("stats") or {}
    plots = [f for f in figures if f.kind != "render"]
    numbering = count(1)
    top = [f for f in plots if f.layer is None]
    top_html = _figures(top, numbering, assets_rel)
    layers = []
    started = False
    for layer in ui.get("layers", []):
        figs = [f for f in plots if f.layer == layer["i"]]
        first = layer.get("status") != "not_run" and not started
        started = started or first
        layers.append(_layer(layer, stats, figs, numbering, assets_rel, first))
    controls = controls_table(ui.get("controls") or [])
    controls_html = (
        f'<section data-testid="controls">{_block(controls)}</section>' if controls else ""
    )
    errors_html = (
        '<div class="errors">' + "<br>".join(e(x) for x in errors) + "</div>" if errors else ""
    )
    scope = "".join(f"<div>{e(x)}</div>" for x in limitations)
    version = (ui.get("record") or {}).get("pahVersion", __version__)
    foot = (
        f'<footer class="foot">{scope}<div>pah {e(version)}'
        " · generated from record.json · UI record ui_record.json · provenance graph graph.svg"
        "</div></footer>"
    )
    summary = (
        f'<section data-testid="summary"><div class="section-head"><h2>Summary</h2>'
        f"</div>{_keys(ui)}{_strip(ui)}"
        f"{top_html}</section>"
    )
    content = (
        f'<div class="content">{summary}{_renders(ui, figures, assets_rel)}{"".join(layers)}'
        f"{controls_html}{_provenance(ui.get('sources') or [])}{_thresholds(ui)}"
        f"{_files(files, assets_rel)}{errors_html}{foot}</div>"
    )
    body = (
        f'<main class="page" data-testid="report" data-state="{e(v.get("outcome", "pending"))}">'
        f'{_header(ui, title)}<div class="layout">{_sidebar(ui)}{content}</div></main>'
    )
    return _doc(f"{title} · {ui.get('id', '')}", body)


def _total(ui: Mapping[str, Any]) -> dict[str, int]:
    total: dict[str, int] = {}
    for layer in ui.get("layers", []):
        for k, n in (layer.get("counts") or {}).items():
            total[k] = total.get(k, 0) + int(n)
    return total


# ---- batch --------------------------------------------------------------------------------


def render_batch_html(
    report: BatchReport,
    *,
    outcomes: Mapping[str, str],
    links: Mapping[str, str],
    figures: Sequence[FigureEntry] = (),
) -> str:
    """Batch summary: one row per target with verdict chip, counts and a link to its report."""
    rows = []
    for t in report.targets:
        outcome = outcomes.get(t.name)
        verdict = chip(outcome, attr="o") if outcome else '<span class="muted">not run</span>'
        link = links.get(t.name)
        name = f'<a href="{e(link)}">{e(t.name)}</a>' if link else e(t.name)
        note = f'<span class="muted"> · {e(t.error)}</span>' if t.error else ""
        rows.append(
            f'<tr data-testid="target-row" data-target="{e(t.name)}" '
            f'data-state="{e(outcome or "not_run")}"><td>{name}{note}</td>'
            f"<td>{text(t.task)}</td><td>{verdict}</td>"
            f"<td>{counts_html(t.counts) if t.counts else na()}</td>"
            f"<td>{text(t.run_id)}</td></tr>"
        )
    head = (
        "<thead><tr><th>target</th><th>task</th><th>verdict</th><th>checks</th>"
        "<th>run</th></tr></thead>"
    )
    flagged = [c for c in report.check_summary if c.targets_stop or c.targets_warn]
    flagged_rows = "".join(
        f'<tr><td>{e(c.check_id)}</td><td class="num">{c.layer}</td>'
        f'<td class="num">{c.counts.get("stop", 0)}</td>'
        f'<td class="num">{c.counts.get("warn", 0)}</td>'
        f"<td>{text(', '.join(c.targets_stop) or None)}</td>"
        f"<td>{text(', '.join(c.targets_warn) or None)}</td></tr>"
        for c in flagged
    )
    flagged_html = (
        '<section data-testid="flagged"><div class="section-head"><h2>Checks that stopped or '
        f'warned</h2><span class="mono muted">{len(flagged)} checks</span></div>'
        '<table class="data"><thead><tr><th>check</th><th class="num">layer</th>'
        '<th class="num">stop</th><th class="num">warn</th><th>targets with stop</th>'
        f"<th>targets with warn</th></tr></thead><tbody>{flagged_rows}</tbody></table></section>"
        if flagged
        else ""
    )
    verdicts = " · ".join(f"{k} {n}" for k, n in sorted(report.verdict_counts.items()))
    created = fmt.when(report.started_at.isoformat())
    body = f"""<main class="page" data-testid="batch-report">
<header class="head"><div class="doc-head"><div>
<div class="eyebrow">Prediction assurance · batch report</div>
<h1 class="doc-title">{e(report.name)}</h1></div>
<div class="doc-id mono">{e(report.batch_id)}<br>{text(created)}</div></div>
<dl class="meta"><div><dt>Targets</dt><dd class="mono">{len(report.targets)}</dd></div>
<div><dt>Verdicts</dt><dd class="mono">{e(verdicts)}</dd></div>
<div><dt>Checks</dt><dd class="mono">{len(report.checks)}</dd></div>
<div><dt>pah</dt><dd class="mono">{e(report.pah_version)}</dd></div></dl></header>
<div class="content">
<section data-testid="targets"><div class="section-head"><h2>Targets</h2></div>
<table class="data">{head}<tbody>{"".join(rows)}</tbody></table></section>
{flagged_html}
{_figures(list(figures), count(1), "")}
<footer class="foot">{"".join(f"<div>{e(x)}</div>" for x in report.limitations)}</footer>
</div></main>"""
    return _doc(f"Batch report · {report.name}", body)


def visible_text(html: str) -> str:
    """Text a reader sees (no style, script or attributes), one line per block, for the lint."""
    from html.parser import HTMLParser

    class _Text(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.parts: list[str] = []
            self._skip = 0

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag in ("style", "script", "title"):
                self._skip += 1
            if tag in ("div", "tr", "p", "br", "section", "h1", "h2", "h3", "figcaption", "li"):
                self.parts.append("\n")

        def handle_endtag(self, tag: str) -> None:
            if tag in ("style", "script", "title"):
                self._skip -= 1

        def handle_data(self, data: str) -> None:
            if not self._skip:
                self.parts.append(data)

    parser = _Text()
    parser.feed(html)
    return "".join(parser.parts)
