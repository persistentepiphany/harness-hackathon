"""Write the HTML scene pages and the shot list for demo film C.

Usage: python3 scenes.py <work_dir>   (run render_twelve.py and shoot_live.js first)
Writes <work>/html/*.html and <work>/shots.json. Every number on a page is read from a run record
or a bench file named in the page's source tag.
"""

from __future__ import annotations

import csv
import html
import json
import sys
from pathlib import Path

ROOT = Path("/home/user/harness-hackathon")
RUN3 = ROOT / "bench/runs/2026-10-17T1859Z-849c856"
CDK2 = RUN3 / "harness/cdk2_pert_boltz2/run"
RUNS = ["2026-10-17T1611Z-426bfe9", "2026-10-17T1752Z-2f5a1c7", "2026-10-17T1859Z-849c856"]
SYSTEMS = [("cdk2", "CDK2"), ("ftse", "FtsE"), ("mek1", "MEK1"), ("glc", "glucose DH")]
SITE = "persistentepiphany--pah-web.us-east.modal.run"

WORK = Path(sys.argv[1])
FONTS = WORK / "fonts"
H = WORK / "html"
H.mkdir(parents=True, exist_ok=True)

CSS = f"""
@font-face {{ font-family: Geist; src: url('file://{FONTS}/Geist-Regular.ttf'); font-weight: 400; }}
@font-face {{ font-family: Geist; src: url('file://{FONTS}/Geist-Medium.ttf'); font-weight: 500; }}
@font-face {{ font-family: Geist; src: url('file://{FONTS}/Geist-SemiBold.ttf'); font-weight: 600; }}
@font-face {{ font-family: 'Geist Mono'; src: url('file://{FONTS}/GeistMono-Regular.ttf'); font-weight: 400; }}
@font-face {{ font-family: 'Geist Mono'; src: url('file://{FONTS}/GeistMono-Medium.ttf'); font-weight: 500; }}
:root {{ --canvas:#F7F7F4; --surface:#FFFFFF; --line:#E6E6E1; --line2:#EFEFEB; --ink:#1A1A18;
  --ink2:#55554F; --muted:#8B8B85; --faint:#B9B9B3; --accent:#B07E2C; --accentd:#8E6420;
  --pass:#3B8A58; --warn:#C28A1A; --stop:#C4513B; --dock:#5B7FA6; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 1920px; height: 1080px; background: var(--canvas); color: var(--ink);
  font-family: Geist, sans-serif; overflow: hidden; }}
.pic {{ position: absolute; left: 0; top: 0; width: 1920px; height: 940px; padding: 96px 120px 0; }}
.band {{ position: absolute; left: 0; top: 940px; width: 1920px; height: 140px;
  border-top: 1px solid var(--line); }}
.tag {{ position: absolute; right: 80px; bottom: 26px; font: 400 18px 'Geist Mono', monospace;
  color: var(--muted); text-align: right; max-width: 560px; line-height: 1.35; }}
.mono {{ font-family: 'Geist Mono', monospace; }}
.eyebrow {{ font: 500 22px 'Geist Mono', monospace; color: var(--accentd); letter-spacing: .04em;
  text-transform: uppercase; margin-bottom: 28px; }}
h1 {{ font-weight: 600; font-size: 64px; line-height: 1.12; letter-spacing: -0.02em; max-width: 1500px; }}
h2 {{ font-weight: 600; font-size: 48px; line-height: 1.15; letter-spacing: -0.015em; }}
.card {{ background: var(--surface); border: 1px solid var(--line); border-radius: 8px; }}
.dot {{ display: inline-block; width: 14px; height: 14px; border-radius: 50%; }}
.pass {{ color: var(--pass); }} .warn {{ color: var(--warn); }} .stop {{ color: var(--stop); }}
.skip {{ color: var(--muted); }}
.bg-pass {{ background: var(--pass); }} .bg-warn {{ background: var(--warn); }}
.bg-stop {{ background: var(--stop); }} .bg-skip {{ background: var(--faint); }}
img.fig {{ display: block; object-fit: contain; }}
"""


def page(name: str, body: str, tag: str = "") -> str:
    t = f'<div class="tag">{tag}</div>' if tag else ""
    doc = (f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head>"
           f"<body>{body}<div class='band'>{t}</div></body></html>")
    (H / f"{name}.html").write_text(doc)
    return name


def esc(s: str) -> str:
    return html.escape(s)


def logo(size: int = 64) -> str:
    r = size * 0.22
    inner = size * 0.36
    o = (size - inner) / 2
    return (f"<svg width='{size}' height='{size}' viewBox='0 0 {size} {size}'>"
            f"<rect x='2' y='2' width='{size-4}' height='{size-4}' rx='{r}' fill='none' stroke='#1A1A18' stroke-width='3'/>"
            f"<rect x='{o}' y='{o}' width='{inner}' height='{inner}' rx='{inner*0.2}' fill='#B07E2C'/></svg>")


def file_url(p: Path) -> str:
    return "file://" + str(p)


# ---------------------------------------------------------------- data from records
TW = ROOT / "media/figures/twelve"
TILES = json.loads((TW / "twelve.json").read_text())
assert len(TILES) == 12 and all(t["arm_A"] == "valid" and t["arm_B"] == "invalid" for t in TILES)
ORDER = ["cdk2", "ftse", "mek1", "glc"]
TILES.sort(key=lambda t: (t["run"], ORDER.index(t["system"])))
T3 = next(t for t in TILES if t["system"] == "cdk2" and t["run"] == 3)

shots: list[dict] = []


def shot(name: str, dur: float, caps: list[tuple[float, str]] | None = None, xf: float = 0.5,
         sfx: str = "whoosh", kind: str = "still", end: float | None = None) -> None:
    shots.append({"name": name, "dur": dur, "caps": caps or [], "xf": xf, "sfx": sfx, "kind": kind, "end": end})


def center(body: str) -> str:
    return (f"<div class='pic' style='display:flex;flex-direction:column;justify-content:center;align-items:center;"
            f"padding:0 120px;text-align:center'>{body}</div>")


# ---------------------------------------------------------------- 1 problem
page("p1_problem", center(
    "<div style='font:600 76px Geist;letter-spacing:-0.02em;line-height:1.15;max-width:1500px'>Biomolecular models give "
    "<span style='color:var(--pass)'>confident scores</span> to <span style='color:var(--stop)'>physically implausible poses.</span></div>"))
shot("p1_problem", 7.0, [], xf=0.0, sfx="")

# ---------------------------------------------------------------- 2 PoseBusters
page("p2_pb", center(f"""
  <div class='card' style='padding:56px 72px;max-width:1380px;text-align:left'>
    <div class='mono' style='font-size:24px;color:var(--accentd)'>Chem. Sci. 2024 · doi:10.1039/d3sc04185a</div>
    <div style='font:600 46px Geist;line-height:1.2;margin-top:22px'>PoseBusters: AI-based docking methods fail to generate physically valid poses or generalise to novel sequences</div>
    <div style='font-size:30px;color:var(--ink2);margin-top:22px'>Buttenschoen M, Morris GM, Deane CM</div>
    <div style='font-size:32px;margin-top:40px'>RMSD alone misses physically implausible poses.</div>
  </div>"""), "Chem. Sci. 2024, 15(9), 3130–3139")
shot("p2_pb", 6.0, [(0.5, "PoseBusters showed it in 2024.")])

# ---------------------------------------------------------------- 3 before: flow, built up step by step
def box(inner: str, w: int, vis: bool, col: str = "var(--line)") -> str:
    return (f"<div class='card' style='width:{w}px;padding:26px 28px;border:2px solid {col};opacity:{1 if vis else 0};"
            f"text-align:center'>{inner}</div>")


def arrow(vis: bool) -> str:
    return f"<div style='font:400 54px Geist;color:var(--muted);opacity:{1 if vis else 0}'>&#8594;</div>"


def flow(cells: list[str], n: int) -> str:
    out = []
    for i, c in enumerate(cells):
        if i:
            out.append(arrow(i < n))
        out.append(c.replace("__VIS__", "1" if i < n else "0"))
    return "<div style='display:flex;align-items:center;justify-content:center;gap:26px;margin-top:70px'>" + "".join(out) + "</div>"


IN_BOX = ("<div class='card' style='width:300px;padding:30px 24px;opacity:__VIS__;text-align:center'>"
          "<div style='font:500 22px Geist Mono;color:var(--muted)'>input</div>"
          "<div style='font:600 40px Geist;margin-top:10px'>CDK2 + ATP</div></div>")
c = T3["confidence"]
BEFORE = [
    IN_BOX,
    ("<div class='card' style='width:330px;padding:30px 24px;opacity:__VIS__;text-align:center'>"
     "<div style='font:500 22px Geist Mono;color:var(--muted)'>model</div>"
     "<div style='font:600 32px Geist;margin-top:10px;line-height:1.35'>Boltz-2<br>DiffDock-L<br>Chai-1</div></div>"),
    ("<div class='card' style='width:340px;padding:30px 24px;opacity:__VIS__;text-align:center;border:2px solid var(--pass)'>"
     "<div style='font:500 22px Geist Mono;color:var(--muted)'>score</div>"
     f"<div class='mono pass' style='font-size:36px;margin-top:12px;line-height:1.4'>ipTM {c['ligand_iptm']:.2f}<br>pLDDT {c['pocket_plddt']:.0f}</div></div>"),
    (f"<div class='card' style='width:470px;overflow:hidden;opacity:__VIS__;border:2px solid var(--stop);position:relative'>"
     f"<img src='{file_url(TW / T3['png'])}' style='display:block;width:100%;height:330px;object-fit:cover'>"
     f"<div style='position:absolute;left:0;right:0;bottom:0;background:rgba(255,255,255,.92);padding:10px 16px;font:600 26px Geist;color:var(--stop)'>"
     f"wrong pose · {T3['contacts_recovered']} of {T3['contacts_reference']} contacts</div></div>"),
]
TAGB = "CDK2 1B38, Boltz-2, bench run 3, seed 8<br>facts/cdk2_pert_boltz2.json"
for n in range(1, 5):
    page(f"b{n}", f"""
<div class='pic' style='padding:230px 80px 0'>
  <div class='eyebrow' style='text-align:center'>Before</div>
  {flow(BEFORE, n)}
</div>""", TAGB)
shot("b1", 2.3, [(0.3, "Before: an input,")], xf=0.5)
shot("b2", 2.0, [(0.1, "a model,")], xf=0.3, sfx="tick")
shot("b3", 2.2, [(0.1, "a confident score,")], xf=0.3, sfx="tick")
shot("b4", 4.2, [(0.3, "and the wrong pose. The score stays high.")], xf=0.3, sfx="tick")

# ---------------------------------------------------------------- 4 with the harness
LABELS = ["Provenance", "Input integrity", "Applicability", "PoseBusters", "PLIP contacts", "Torsion strain",
          "Seed stability", "Controls"]


def harness(n: int) -> str:
    chips = "".join(f"<div class='card' style='padding:20px 18px;font:600 28px Geist;text-align:center;opacity:{1 if n >= 2 else 0}'>{l}</div>"
                    for l in LABELS)
    hb = ("<div class='card' style='width:330px;padding:30px 24px;text-align:center;border:2px solid var(--accent)'>"
          f"<div style='display:flex;justify-content:center'>{logo(56)}</div>"
          "<div style='font:600 38px Geist;margin-top:12px'>Dock Harness</div></div>")
    vb = (f"<div class='card' style='width:330px;padding:30px 24px;text-align:center;opacity:{1 if n >= 3 else 0};border:2px solid var(--stop)'>"
          "<div style='font:500 22px Geist Mono;color:var(--muted)'>verdict</div>"
          "<div style='font:600 40px Geist;color:var(--stop);margin-top:10px'>stop</div>"
          "<div style='font-size:22px;color:var(--ink2);margin-top:6px'>with the evidence</div></div>")
    return f"""
<div class='pic' style='padding:170px 80px 0'>
  <div class='eyebrow' style='text-align:center'>With the harness</div>
  <div style='display:flex;align-items:center;justify-content:center;gap:26px;margin-top:40px'>
    {IN_BOX.replace('__VIS__', '1')}{arrow(True)}{hb}{arrow(n >= 3)}{vb}
  </div>
  <div style='display:grid;grid-template-columns:repeat(4,300px);gap:18px;justify-content:center;margin-top:56px'>{chips}</div>
</div>"""


for n in range(1, 4):
    page(f"h{n}", harness(n), "README.md check tables<br>CDK2 verdict: bench run 3 record.json")
shot("h1", 2.6, [(0.4, "With the harness:")], xf=0.5)
shot("h2", 3.6, [(0.2, "it checks the inputs, the physics and the chemistry,")], xf=0.3, sfx="tick")
shot("h3", 4.2, [(0.2, "and returns a verdict with its evidence.")], xf=0.3, sfx="tick")

# ---------------------------------------------------------------- 5 the result
def tile(t: dict, arm: str) -> str:
    lab = "glucose DH" if t["system"] == "glc" else t["label"]
    if arm == "A":
        band = "<div style='background:var(--stop);color:#fff;padding:9px 12px;font:600 21px Geist'>called valid</div>"
    else:
        pb = t["posebusters"]
        why = (f"PoseBusters {pb['passed']}/{pb['total']}" if pb["failed"]
               else f"contacts {t['contacts_recovered']}/{t['contacts_reference']}")
        band = (f"<div style='background:var(--pass);color:#fff;padding:9px 12px;font:600 21px Geist;display:flex;justify-content:space-between'>"
                f"<span>rejected</span><span class='mono' style='font-weight:400;font-size:18px'>{why}</span></div>")
    return (f"<div class='card' style='overflow:hidden'>"
            f"<img src='{file_url(TW / t['png'])}' style='display:block;width:100%;height:150px;object-fit:cover'>"
            f"<div style='padding:7px 12px;font:600 19px Geist'>{esc(lab)} {t['pdb']}"
            f"<span class='mono' style='font-weight:400;font-size:16px;color:var(--ink2)'>&#8194;run {t['run']}</span></div>{band}</div>")


def result(arm: str) -> str:
    grid = "".join(tile(t, arm) for t in TILES)
    rows = [("score only", "0/12", "var(--stop)")]
    if arm == "B":
        rows.append(("harness fact file", "12/12", "var(--pass)"))
    card = "".join(f"<div style='margin-top:30px'><div style='font-size:24px;color:var(--ink2)'>{a}</div>"
                   f"<div class='mono' style='font-size:84px;line-height:1.05;color:{col}'>{b}</div></div>" for a, b, col in rows)
    return f"""
<div class='pic' style='padding:40px 60px 0'>
  <h2 style='font-size:46px'>12 wrong without the harness, 12 right with it</h2>
  <div style='font-size:22px;color:var(--ink2);margin-top:10px'>CDK2 1B38 · FtsE 8X61 · MEK1 7XLP · glucose dehydrogenase 2VWH ·
    pocket residues cut to glycine (glucose DH: ligand methylated) · our perturbation benchmark, GLM-4.6 agent</div>
  <div style='display:grid;grid-template-columns:1fr 330px;gap:28px;margin-top:22px'>
    <div style='display:grid;grid-template-columns:repeat(4,1fr);gap:12px'>{grid}</div>
    <div class='card' style='padding:28px 30px'>
      <div style='font:600 26px Geist'>GLM-4.6 agent</div>
      <div style='font-size:20px;color:var(--muted);margin-top:4px'>perturbed poses rejected</div>
      {card}
    </div>
  </div>
</div>"""


TAGR = "bench/runs/*/results/decisions.csv, facts/<br>majority of 3 repeats · media/figures/twelve"
page("r_A", result("A"), TAGR)
page("r_B", result("B"), TAGR)
shot("r_A", 10.0, [(0.5, "Our benchmark: 12 Boltz-2 poses with the pocket broken."),
                   (5.0, "On the score alone, the agent called all 12 valid.")])
shot("r_B", 14.0, [(0.6, "With the harness fact file, it rejected all 12."),
                   (5.2, "The reason is in the facts: lost contacts, a failed PoseBusters test."),
                   (10.4, "The score never showed it.")], xf=0.6)

# ---------------------------------------------------------------- 6 the product (live takes)
shot("UI_input", 0, kind="ui", xf=0.6)
shot("UI_report", 0, kind="ui", xf=0.5)
shot("UI_ensemble", 0, kind="ui", xf=0.5, end=12.9)
shot("UI_evidence", 0, kind="ui", xf=0.5)
shot("UI_document", 0, kind="ui", xf=0.5)
shot("UI_agent", 0, kind="ui", xf=0.5, end=3.7)

# ---------------------------------------------------------------- 7 close
page("s8_close", f"""
<div class='pic' style='display:flex;flex-direction:column;justify-content:center;padding-top:0;padding-left:160px'>
  <div style='margin-bottom:40px'>{logo(72)}</div>
  <div style='font-weight:600;font-size:84px;letter-spacing:-0.025em;line-height:1.12;max-width:1500px'>
    Every number traceable to a check, a tool and a <span style='color:var(--accent)'>source.</span></div>
  <div class='mono' style='font-size:34px;color:var(--ink2);margin-top:52px'>{SITE}</div>
</div>""", "Dock Harness · pah")
shot("s8_close", 6.0, [], sfx="whoosh")

page("zz_uiband", "", f"{SITE}<br>live web UI, recorded 2026-10-18")
(WORK / "shots.json").write_text(json.dumps(shots, indent=1))
print(len(shots), "shots;", sum(s["dur"] or 0 for s in shots), "s of stills before overlaps")
