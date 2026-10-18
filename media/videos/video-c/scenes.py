"""Write the HTML scene pages and the shot list for demo film C.

Usage: python3 scenes.py <work_dir>
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
def boltz_pert_decisions() -> list[dict]:
    out = []
    for i, rid in enumerate(RUNS, 1):
        rows = list(csv.DictReader(open(ROOT / "bench/runs" / rid / "results/decisions.csv")))
        for key, label in SYSTEMS:
            sel = [r for r in rows if r["system"] == f"{key}_pert" and r["executor"] == "boltz2"]
            a = [r["verdict"] for r in sel if r["arm"] == "A"]
            b = [r["verdict"] for r in sel if r["arm"] == "B"]
            maj = lambda v: max(set(v), key=v.count)  # noqa: E731
            out.append({"run": i, "label": label, "A": maj(a), "B": maj(b)})
    return out


DEC = boltz_pert_decisions()
assert len(DEC) == 12 and all(d["A"] == "valid" for d in DEC) and all(d["B"] == "invalid" for d in DEC)

REC = json.loads((CDK2 / "record.json").read_text())
FIND = {f["check_id"]: f for f in REC["findings"]}

shots: list[dict] = []


def shot(name: str, dur: float, caps: list[tuple[float, str]] | None = None, xf: float = 0.5,
         zoom: float = 0.0, sfx: str = "whoosh") -> None:
    shots.append({"name": name, "dur": dur, "caps": caps or [], "xf": xf, "zoom": zoom, "sfx": sfx})


# ---------------------------------------------------------------- 1 title
page("s1_title", f"""
<div class='pic' style='display:flex;flex-direction:column;justify-content:center;padding-top:0;padding-left:160px'>
  <div style='margin-bottom:40px'>{logo(84)}</div>
  <div style='font-weight:600;font-size:118px;letter-spacing:-0.03em;line-height:1'>Dock <span style='color:var(--accent)'>Harness</span></div>
  <div style='font-weight:500;font-size:46px;color:var(--ink2);margin-top:34px'>Does this prediction support the claim?</div>
</div>""", "Prediction Assurance Harness (pah)")
shot("s1_title", 5.0, [], xf=0.0, sfx="")

# ---------------------------------------------------------------- 2 problem
page("s2a_auc", """
<div class='pic'>
  <div class='eyebrow'>The problem</div>
  <h1>Model confidence does not establish that a pose is valid.</h1>
  <div style='display:flex;gap:64px;margin-top:84px;align-items:flex-end'>
    <div class='mono' style='font-size:150px;font-weight:500;line-height:.9;color:var(--accentd)'>&#8776;75</div>
    <div style='font-size:34px;line-height:1.4;color:var(--ink2);padding-bottom:6px'>
      ROC AUC of the best confidence metrics<br>for finding poses within 2&#8201;&#197;,<br>
      on a prospective set of <span class='mono' style='color:var(--ink)'>489</span> complexes</div>
  </div>
</div>""", "docs/SPECIFICATION.md, Overview<br>(published evaluations)")
shot("s2a_auc", 9.0, [(0.5, "A high confidence score does not show that a pose is right."),
                       (4.4, "In published evaluations the best confidence metrics reach about 75 ROC AUC.")])


def tiles(arm: str, show_b: bool) -> str:
    cells = []
    for d in DEC:
        v = d[arm]
        col = "var(--stop)" if (arm == "A") else "var(--pass)"
        word = "called valid" if v == "valid" else "rejected"
        cells.append(f"<div style='background:{col};border-radius:6px;height:84px;color:#fff;display:flex;"
                     f"flex-direction:column;justify-content:center;align-items:center;gap:6px'>"
                     f"<div style='font:600 24px Geist'>{word}</div>"
                     f"<div class='mono' style='font-size:17px;opacity:.9'>{esc(d['label'])} · run {d['run']}</div></div>")
    return "<div style='display:grid;grid-template-columns:repeat(6,1fr);gap:10px'>" + "".join(cells) + "</div>"


def tile_rows(show_b: bool) -> str:
    rows = [("confidence score only", tiles("A", show_b))]
    if show_b:
        rows.append(("harness fact file", tiles("B", show_b)))
    return "".join(
        f"<div style='display:grid;grid-template-columns:250px 1fr;gap:24px;align-items:center;margin-top:26px'>"
        f"<div style='font:500 26px Geist;color:var(--ink2);text-align:right'>{lab}</div>{t}</div>" for lab, t in rows)


page("s2b_tiles", f"""
<div class='pic'>
  <div class='eyebrow'>Perturbation benchmark</div>
  <h2>12 Boltz-2 poses after the pocket contacts were cut to glycine</h2>
  <div style='font-size:30px;color:var(--ink2);margin-top:18px'>An LLM agent saw only the confidence score (ligand ipTM, pocket pLDDT).</div>
  <div style='margin-top:70px'>{tile_rows(False)}</div>
  <div style='margin-top:40px;margin-left:274px;font-size:28px;color:var(--ink2)'>Every perturbed pose is invalid by construction.</div>
</div>""", "bench/runs/*/results/decisions.csv<br>4 systems × 3 runs, majority of 3 repeats")
shot("s2b_tiles", 10.2, [(0.6, "Given only the score, an LLM agent called all 12 perturbed Boltz-2 poses valid."),
                          (5.4, "The pockets were cut to glycine, so all of these poses are invalid.")])

# ---------------------------------------------------------------- 3 layers
LAYERS = [
    ("L0", "Provenance", "where every input came from, with sha256 and version"),
    ("L1", "Input integrity", "sequence, ligand and chain identity match the sources"),
    ("L2", "Input adequacy", "MSA, pocket, cofactors, protonation, docking box"),
    ("L3", "Applicability", "training cutoff, exposure, modality, endpoint"),
    ("L4", "Output validity", "PoseBusters, torsion strain, interactions"),
    ("L5", "Output support", "confidence, seeds, clusters, cross-method agreement, controls"),
]


def layer_page(n: int) -> str:
    rows = []
    for i, (lid, name, desc) in enumerate(LAYERS):
        vis = i < n
        grp = "inputs" if i < 3 else ("applicability" if i == 3 else "outputs")
        col = {"inputs": "var(--dock)", "applicability": "var(--accent)", "outputs": "var(--pass)"}[grp]
        rows.append(
            f"<div class='card' style='display:grid;grid-template-columns:110px 380px 1fr;align-items:center;"
            f"height:92px;padding:0 36px;margin-bottom:14px;border-left:6px solid {col};opacity:{1 if vis else 0}'>"
            f"<div class='mono' style='font-size:34px;font-weight:500;color:{col}'>{lid}</div>"
            f"<div style='font-size:36px;font-weight:600'>{name}</div>"
            f"<div style='font-size:27px;color:var(--ink2)'>{desc}</div></div>")
    brk = []
    if n >= 1:
        brk.append(("Before any model runs", 0, 3, "var(--dock)"))
    if n >= 5:
        brk.append(("After the run", 4, 2, "var(--pass)"))
    labels = "".join(
        f"<div style='position:absolute;left:0;top:{s*106}px;height:{c*106-14}px;width:250px;border-right:3px solid {col};"
        f"display:flex;align-items:center;justify-content:flex-end;padding-right:22px;font:500 26px Geist;"
        f"color:{col};text-align:right;opacity:{1 if (s == 0 or n >= 5) else 0}'>{t}</div>" for t, s, c, col in brk)
    return page(f"s3_layers{n}", f"""
<div class='pic'>
  <div class='eyebrow'>How it works</div>
  <h2>Six layers of checks</h2>
  <div style='position:relative;margin-top:56px;padding-left:290px'>
    <div style='position:absolute;left:0;top:0;width:250px;height:640px'>{labels}</div>
    {''.join(rows)}
  </div>
</div>""", "docs/SPECIFICATION.md, layers 0 to 5")


for n in range(1, 7):
    layer_page(n)
shot("s3_layers1", 2.2, [(0.3, "Six layers. The first three check the inputs before any model runs.")])
shot("s3_layers2", 1.6, xf=0.3, sfx="tick")
shot("s3_layers3", 1.8, xf=0.3, sfx="tick")
shot("s3_layers4", 3.2, [(0.2, "Layer three: does the model apply to this target?")], xf=0.3, sfx="tick")
shot("s3_layers5", 2.0, [(0.2, "Layers four and five check the outputs.")], xf=0.3, sfx="tick")
shot("s3_layers6", 2.6, xf=0.3, sfx="tick")


def check_row(cid: str) -> str:
    f = FIND[cid]
    g = f["gate"]
    th = f["thresholds"][0] if f["thresholds"] else None
    if th:
        origin = th["origin"].split(";")[0]
        if len(origin) > 74:
            origin = origin[:72].rsplit(" ", 1)[0] + " …"
        thr = (f"<span class='mono'>{esc(th['name'].split('.')[-1])} {esc(th['comparator'])} {th['value']}</span>"
               f"<div style='font-size:21px;color:var(--muted);margin-top:6px'>origin: {esc(origin)}</div>")
    else:
        thr = "<span style='color:var(--faint)'>&#8211;</span>"
    msg = f["message"]
    msg = msg.replace(" in boltz2/seed8/sample0", "").replace("boltz2/seed8/sample0: ", "")
    return (f"<div style='display:grid;grid-template-columns:110px 560px 1fr 520px;align-items:center;gap:24px;"
            f"padding:22px 32px;border-bottom:1px solid var(--line2)'>"
            f"<div class='{g}' style='font:500 26px Geist Mono;display:flex;align-items:center;gap:12px'>"
            f"<span class='dot bg-{g}'></span>{g}</div>"
            f"<div class='mono' style='font-size:23px'>{esc(cid)}</div>"
            f"<div style='font-size:24px;color:var(--ink2)'>{esc(msg)}</div><div style='font-size:24px'>{thr}</div></div>")


page("s3_checks", f"""
<div class='pic'>
  <div class='eyebrow'>Each check</div>
  <h2>pass, warn, stop or skip, with evidence and a threshold with its origin</h2>
  <div class='card' style='margin-top:56px'>
    <div style='display:grid;grid-template-columns:110px 560px 1fr 520px;gap:24px;padding:16px 32px;
      border-bottom:1px solid var(--line);font:500 19px Geist Mono;color:var(--muted);text-transform:uppercase'>
      <div>result</div><div>check</div><div>evidence</div><div>threshold</div></div>
    {check_row('l5.confidence.local')}{check_row('l4.interactions.unsatisfied_polars')}
    {check_row('l5.controls.redocking')}{check_row('l2.msa.depth')}
  </div>
</div>""", "record.json, cdk2_pert · Boltz-2, bench run 3")
shot("s3_checks", 8.3, [(0.6, "Each check returns pass, warn, stop or skip."),
                         (3.4, "It records the evidence and the threshold, and says where the threshold comes from.")])

# ---------------------------------------------------------------- 4 live UI (recorded, inserted by build.py)
shots.append({"name": "UI", "dur": None, "caps": [], "xf": 0.5, "zoom": 0, "sfx": "whoosh"})

# ---------------------------------------------------------------- 5 files
ST = ROOT / "videos/public/stills"
page("s5_pymol", f"""
<div class='pic'>
  <div class='eyebrow'>Files every run writes</div>
  <h2>Up to 10 structures rendered with PyMOL, main structure first</h2>
  <div style='display:grid;grid-template-columns:1fr 1fr 1.55fr;gap:24px;margin-top:56px;align-items:start'>
    <div><img class='fig card' style='width:100%;height:440px;object-fit:cover' src='{file_url(ST/"3ptb-overview.png")}'>
      <div class='mono' style='font-size:20px;color:var(--muted);margin-top:12px'>3ptb-overview.png</div></div>
    <div><img class='fig card' style='width:100%;height:440px;object-fit:cover' src='{file_url(ST/"seed0-overview.png")}'>
      <div class='mono' style='font-size:20px;color:var(--muted);margin-top:12px'>seed0-overview.png</div></div>
    <div><img class='fig card' style='width:100%;height:440px;object-fit:contain;background:#fff' src='{file_url(ST/"molstar-overlay.png")}'>
      <div class='mono' style='font-size:20px;color:var(--muted);margin-top:12px'>overlay of the seed poses (Mol*)</div></div>
  </div>
</div>""", "run ui-vina: 3PTB, AutoDock Vina 1.2.7, 5 seeds<br>.pse and PNG per structure")
shot("s5_pymol", 5.0, [(0.4, "Each run renders up to 10 structures as PyMOL sessions and PNG files.")], zoom=0.025)

page("s5_report", f"""
<div class='pic' style='padding-top:60px'>
  <div style='display:flex;gap:48px'>
    <div style='width:520px;padding-top:36px'>
      <div class='eyebrow'>report.html</div>
      <h2>Generated from the run record only</h2>
      <div style='font-size:28px;color:var(--ink2);margin-top:28px;line-height:1.45'>Verdict, gates per layer, each check with its value, threshold and origin, then provenance.</div>
    </div>
    <img class='card' style='width:1160px;height:820px;object-fit:cover;object-position:top' src='{file_url(WORK/"stills/report_shot.png")}'>
  </div>
</div>""", "cdk2_pert_boltz2/run/report.html, bench run 3")
shot("s5_report", 5.6, [(0.4, "report.html is written from the run record, with every value, threshold and origin.")])

page("s5_graph", f"""
<div class='pic' style='padding-top:60px'>
  <div style='display:flex;gap:48px'>
    <div style='width:520px;padding-top:36px'>
      <div class='eyebrow'>graph.json · graph.mmd · graph.svg</div>
      <h2>Provenance graph</h2>
      <div style='font-size:28px;color:var(--ink2);margin-top:28px;line-height:1.45'>Sources, files, tools, checks, findings and the verdict, with sha256 checksums and versions.</div>
    </div>
    <div class='card' style='width:1160px;height:820px;display:flex;align-items:center;justify-content:center;overflow:hidden'>
</div>
  </div>
</div>""", "cdk2_pert_boltz2/run/graph.svg, bench run 3")
shot("s5_graph", 6.4, [(0.4, "The provenance graph links sources, files, tools, checks and the verdict, with checksums.")])

FIG = CDK2 / "figures"
page("s5_figs", f"""
<div class='pic'>
  <div class='eyebrow'>figures/</div>
  <h2>PoseBusters tests, seed spread and contacts</h2>
  <div style='display:grid;grid-template-columns:0.8fr 1.3fr 0.85fr;gap:24px;margin-top:44px;align-items:center'>
    <img class='fig card' style='width:100%;height:640px;padding:12px' src='{file_url(FIG/"posebusters_grid.png")}'>
    <img class='fig card' style='width:100%;height:640px;padding:12px' src='{file_url(FIG/"seed_spread.png")}'>
    <img class='fig card' style='width:100%;height:640px;padding:12px' src='{file_url(FIG/"interactions.png")}'>
  </div>
</div>""", "cdk2_pert_boltz2/run/figures/, bench run 3")
shot("s5_figs", 5.2, [(0.4, "Figures for PoseBusters tests, seed spread and contacts come from the same record.")])

# ---------------------------------------------------------------- 6 benchmark
SYS_ROWS = [("FtsE", "8X61", "ATP", "7 contacts to glycine"), ("CDK2", "1B38", "ATP", "13 contacts to glycine"),
            ("MEK1", "7XLP", "FZC", "11 contacts to glycine"),
            ("glucose dehydrogenase", "2VWH", "BGC", "3 ring hydroxyls methylated")]
sysrows = "".join(
    f"<div style='display:grid;grid-template-columns:330px 120px 110px 1fr;padding:18px 28px;border-bottom:1px solid var(--line2);font-size:27px'>"
    f"<div>{a}</div><div class='mono'>{b}</div><div class='mono'>{c}</div><div style='color:var(--ink2)'>{d}</div></div>"
    for a, b, c, d in SYS_ROWS)
page("s6_design", f"""
<div class='pic'>
  <div class='eyebrow'>Perturbation benchmark · design</div>
  <h2>Wild type and perturbed, from published failure cases</h2>
  <div style='display:grid;grid-template-columns:1.45fr 1fr;gap:48px;margin-top:48px'>
    <div class='card'>
      <div style='display:grid;grid-template-columns:330px 120px 110px 1fr;padding:14px 28px;border-bottom:1px solid var(--line);
        font:500 19px Geist Mono;color:var(--muted);text-transform:uppercase'><div>system</div><div>pdb</div><div>ligand</div><div>perturbation</div></div>
      {sysrows}
    </div>
    <div style='font-size:29px;line-height:1.5;color:var(--ink2)'>
      <div style='margin-bottom:22px'><span style='color:var(--ink);font-weight:500'>Executors</span><br>Boltz-2 and DiffDock-L on Modal A100 GPUs</div>
      <div style='margin-bottom:22px'><span style='color:var(--ink);font-weight:500'>Repeats</span><br><span class='mono'>3</span> runs × <span class='mono'>3</span> seeds</div>
      <div><span style='color:var(--ink);font-weight:500'>Agent</span> (GLM-4.6, temperature 0)<br>arm A: confidence score only<br>arm B: the harness fact file</div>
    </div>
  </div>
</div>""", "bench/README.md<br>runs/*/config/targets.yaml")
shot("s6_design", 9.2, [(0.5, "Four systems, wild type and perturbed, on Boltz-2 and DiffDock-L (Modal A100)."),
                         (4.6, "The agent judges each pose from the score, then from the fact file.")])

page("s6_ba", f"""
<div class='pic'>
  <div class='eyebrow'>Results · run 3, seeds 7, 8, 9</div>
  <h2>Balanced accuracy over 16 predictions</h2>
  <div style='display:grid;grid-template-columns:1fr 1fr;gap:56px;margin-top:48px;align-items:center'>
    <img class='fig card' style='width:100%;height:560px;padding:16px' src='{file_url(RUN3/"results/figures/balanced_accuracy.png")}'>
    <div>
      <div style='display:flex;gap:56px;align-items:flex-end'>
        <div><div style='font-size:26px;color:var(--ink2)'>score only</div>
          <div class='mono' style='font-size:120px;font-weight:500;line-height:1;color:var(--stop)'>0.50</div></div>
        <div><div style='font-size:26px;color:var(--ink2)'>fact file</div>
          <div class='mono' style='font-size:120px;font-weight:500;line-height:1;color:var(--pass)'>0.75</div></div>
      </div>
      <div style='font-size:28px;color:var(--ink2);margin-top:36px;line-height:1.6'>
        fact file 95% CI <span class='mono' style='color:var(--ink)'>0.50 to 1.0</span><br>
        McNemar exact p <span class='mono' style='color:var(--ink)'>0.125</span><br>
        Four systems per state, so the intervals are wide.</div>
    </div>
  </div>
</div>""", "bench/runs/2026-10-17T1859Z-849c856/report.md<br>results/figures/balanced_accuracy.png")
shot("s6_ba", 7.6, [(0.5, "Run 3: balanced accuracy 0.50 from the score, 0.75 with the fact file."),
                     (4.6, "95% CI 0.50 to 1.0, McNemar p 0.125.")])

page("s6_tiles", f"""
<div class='pic'>
  <div class='eyebrow'>Results · all three runs</div>
  <h2>The same 12 perturbed Boltz-2 poses</h2>
  <div style='margin-top:50px'>{tile_rows(True)}</div>
  <div style='margin-top:56px;margin-left:274px;font-size:29px;color:var(--ink2);line-height:1.5'>
    Weakness: the fact file arm also rejected valid poses, most often from DiffDock-L.</div>
</div>""", "bench/runs/*/results/decisions.csv<br>majority of 3 repeats")
shot("s6_tiles", 7.6, [(0.5, "With the fact file, the agent rejected all 12 perturbed Boltz-2 poses."),
                        (4.3, "It also rejected some valid poses, most often DiffDock-L.")])

wt3 = "ipTM 0.978 · pocket pLDDT 95.1"
P = ROOT / "bench/finding/panels"
page("s6_cdk2", f"""
<div class='pic'>
  <div class='eyebrow'>Worked case · CDK2 (1B38), ATP, Boltz-2</div>
  <div style='display:grid;grid-template-columns:1fr 1fr;gap:36px;margin-top:12px'>
    <div><img class='fig card' style='width:100%;height:520px;object-fit:cover' src='{file_url(P/"cdk2_wt.png")}'>
      <div style='font:600 32px Geist;margin-top:22px'>wild type</div>
      <div class='mono' style='font-size:25px;color:var(--ink2);margin-top:10px'>{wt3}</div>
      <div style='font-size:30px;margin-top:12px'>contacts recovered <span class='mono pass'>6 of 9</span></div></div>
    <div><img class='fig card' style='width:100%;height:520px;object-fit:cover' src='{file_url(P/"cdk2_pert.png")}'>
      <div style='font:600 32px Geist;margin-top:22px'>13 pocket contacts cut to glycine</div>
      <div class='mono' style='font-size:25px;color:var(--ink2);margin-top:10px'>ipTM 0.925 · pocket pLDDT 82.3</div>
      <div style='font-size:30px;margin-top:12px'>contacts recovered <span class='mono stop'>1 of 9</span></div></div>
  </div>
</div>""", "values: bench run 3 report.md<br>panels: bench/finding/panels (PyMOL)")
shot("s6_cdk2", 8.4, [(0.4, "CDK2, pocket cut to glycine: ipTM 0.925, pocket pLDDT 82.3."),
                       (3.6, "It recovers 1 of 9 deposited contacts. The wild type recovers 6 of 9.")])

# ---------------------------------------------------------------- 7 tests
def stat(n: str, lab: str) -> str:
    return (f"<div class='card' style='padding:44px 48px'><div class='mono' style='font-size:110px;font-weight:500;line-height:1'>{n}</div>"
            f"<div style='font-size:32px;color:var(--ink2);margin-top:22px'>{lab}</div></div>")


page("s7_tests", f"""
<div class='pic'>
  <div class='eyebrow'>Tests</div>
  <h2>Checked in code and against planted faults</h2>
  <div style='display:grid;grid-template-columns:1fr 1fr 1.25fr;gap:32px;margin-top:80px'>
    {stat('371', 'Python tests (pytest)')}{stat('203', 'web tests (Vitest)')}
    {stat('7 → 7', 'planted input faults give 7 stops')}
  </div>
</div>""", "tests/, web/ (counted 2026-10-18)<br>examples/3ptb_faulty_inputs")
shot("s7_tests", 7.0, [(0.5, "371 Python tests and 203 web tests."),
                        (2.8, "An example with seven planted input faults gives seven stops.")])

# ---------------------------------------------------------------- 8 close
page("s8_close", f"""
<div class='pic' style='display:flex;flex-direction:column;justify-content:center;padding-top:0;padding-left:160px'>
  <div style='margin-bottom:44px'>{logo(72)}</div>
  <div style='font-weight:600;font-size:84px;letter-spacing:-0.025em;line-height:1.12;max-width:1500px'>
    Every number traceable to a check, a tool and a <span style='color:var(--accent)'>source.</span></div>
  <div class='mono' style='font-size:34px;color:var(--ink2);margin-top:56px'>{SITE}</div>
</div>""", "Dock Harness · pah")
shot("s8_close", 6.0, [], sfx="whoosh")

page("zz_uiband", "", f"{SITE}<br>live web UI, recorded 2026-10-18")
(WORK / "shots.json").write_text(json.dumps(shots, indent=1))
print(len(shots), "shots;", sum(s["dur"] or 0 for s in shots), "s of stills before overlaps")
