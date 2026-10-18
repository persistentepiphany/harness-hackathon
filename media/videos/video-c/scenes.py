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
LIVE = WORK / "live"
REC = json.loads((CDK2 / "record.json").read_text())
FIND = {f["check_id"]: f for f in REC["findings"]}
CONF = json.loads(next((RUN3 / "predictions/cdk2_pert/boltz2/seed_8").glob(
    "boltz_results_*/predictions/*/confidence_*_model_0.json")).read_text())
STATS = json.loads((RUN3 / "results/stats.json").read_text())["arms"]["all"]
FACTS3 = json.loads((RUN3 / "facts/cdk2_pert_boltz2.json").read_text())

shots: list[dict] = []


def shot(name: str, dur: float, caps: list[tuple[float, str]] | None = None, xf: float = 0.5,
         sfx: str = "whoosh", kind: str = "still") -> None:
    shots.append({"name": name, "dur": dur, "caps": caps or [], "xf": xf, "sfx": sfx, "kind": kind})


def section(n: int, title: str) -> str:
    return (f"<div class='eyebrow' style='margin-bottom:18px'><span style='color:var(--ink)'>{n}</span>"
            f"&#8195;{esc(title)}</div>")


def short(t: dict) -> str:
    return "glucose DH" if t["system"] == "glc" else t["label"]


def reason(t: dict) -> list[str]:
    out = [f"contacts recovered {t['contacts_recovered']} of {t['contacts_reference']}"]
    pb = t["posebusters"]
    if pb["failed"]:
        out.append(f"PoseBusters fails {pb['total'] - pb['passed']} of {pb['total']} tests")
    elif t["buried_unsatisfied_polars"]:
        n = t["buried_unsatisfied_polars"]
        out.append(f"{n} buried polar atom{'s' if n != 1 else ''} unpaired")
    else:
        out.append(f"torsion strain {t['torsion_strain_kcal']:g} kcal/mol")
    return out


def grid12(arm: str) -> str:
    cells = []
    for t in TILES:
        c = t["confidence"]
        if arm == "A":
            band = ("<div style='background:var(--stop);color:#fff;padding:9px 12px;border-radius:0 0 6px 6px;height:86px'>"
                    "<div style='font:600 19px Geist'>Without the harness: called valid</div>"
                    "<div style='font:400 16px Geist Mono;opacity:.92;margin-top:5px'>agent saw ipTM and pLDDT only</div></div>")
        else:
            r = reason(t)
            band = ("<div style='background:var(--pass);color:#fff;padding:9px 12px;border-radius:0 0 6px 6px;height:86px'>"
                    f"<div style='font:600 19px Geist'>With the fact file: rejected</div>"
                    f"<div style='font:400 15px Geist Mono;opacity:.95;margin-top:4px;line-height:1.3'>{esc(r[0])}<br>{esc(r[1])}</div></div>")
        cells.append(
            f"<div class='card' style='overflow:hidden;position:relative'>"
            f"<img src='{file_url(TW / t['png'])}' style='display:block;width:100%;height:132px;object-fit:cover'>"
            f"<div style='position:absolute;left:0;top:0;background:rgba(255,255,255,.88);padding:5px 10px;"
            f"font:600 18px Geist;border-bottom-right-radius:6px'>{esc(short(t))} {t['pdb']}"
            f"<span style='font:400 15px Geist Mono;color:var(--ink2)'>&#8194;run {t['run']} · seed {t['seed']}</span></div>"
            f"<div class='mono' style='font-size:16px;color:var(--ink2);padding:6px 12px'>ipTM {c['ligand_iptm']:.3f} · pocket pLDDT {c['pocket_plddt']:.1f}</div>"
            f"{band}</div>")
    return ("<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:14px'>"
            + "".join(cells) + "</div>")


TAG12 = ("bench/runs/*/results/decisions.csv, facts/<br>"
         "GLM-4.6, majority of 3 repeats<br>renders: media/figures/twelve")
for arm in ("A", "B"):
    head = ("12 perturbed Boltz-2 predictions" if arm == "A" else "The same 12, judged with the harness fact file")
    page(f"c0_{arm}", f"""
<div class='pic' style='padding:44px 60px 0'>
  <div style='display:flex;align-items:baseline;gap:28px'>
    <h2 style='font-size:42px'>{head}</h2>
    <div style='font-size:22px;color:var(--ink2)'><span style='color:var(--stop)'>&#9679;</span> pocket residues cut to glycine · glucose DH: 3 ring hydroxyls methylated</div>
  </div>
  {grid12(arm)}
</div>""", TAG12)
shot("c0_A", 10.6, [(0.4, "12 perturbed Boltz-2 predictions: four systems, three runs each, every pocket broken on purpose."),
                    (5.6, "Shown only ipTM and pLDDT, an LLM agent called all 12 valid.")], xf=0.0, sfx="")
shot("c0_B", 12.4, [(0.6, "Given the harness fact file, the same agent rejected all 12."),
                    (4.2, "The facts: crystal contacts lost, buried polar atoms unpaired, a failed PoseBusters test."),
                    (9.0, "None of it shows in the confidence score.")], xf=0.6)

# ---------------------------------------------------------------- 1 the problem: study cards
CARDS = [
    ("Chem. Sci. 2024, 15(9), 3130–3139", "PoseBusters: AI-based docking methods fail to generate physically valid poses or generalise to novel sequences",
     "Buttenschoen M, Morris GM, Deane CM", "doi:10.1039/d3sc04185a · arXiv:2308.05777",
     ["5 deep-learning docking methods (DeepDock, DiffDock, EquiBind, TankBind, Uni-Mol) against AutoDock Vina and CCDC Gold",
      "RMSD alone is not sufficient: DL methods often produce physically implausible structures",
      "None yet outperforms classical docking on physical plausibility or on novel sequences"]),
    ("eLife 2026, 15, RP110475 (reviewed preprint)", "Large-scale prospective evaluation of co-folding across hundreds of Mac1–ligand complexes and three virtual screens",
     "Kim J, Correy GJ, Hall BW, … Shoichet BK, Fraser JS", "doi:10.7554/eLife.110475 · bioRxiv 10.64898/2025.12.25.696505",
     ["557 Mac1 ligands, all determined after the training cutoffs",
      "Best confidence score for poses within 2 Å: ROC AUC 0.76 (AF3 ligand pLDDT), 0.73 (Chai-1 ipTM)",
      "AF3 recovered 4 of 19 twisted and 0 of 20 open states, with 8 false-positive twisted states"]),
    ("Nat. Struct. Mol. Biol. 2026, 33, 782–794", "Evaluating generalization in protein–ligand cofolding methods",
     "Škrinjar P, Eberhardt J, Studer G, Tauriello G, Schwede T, Durairaj J", "doi:10.1038/s41594-026-01797-5",
     ["Runs N' Poses: 2,600 protein–ligand systems released after the training cutoff",
      "Four co-folding methods largely memorise ligand poses from their training data"]),
]


def card(j: str, title: str, au: str, doi: str, pts: list[str]) -> str:
    li = "".join(f"<li style='margin-bottom:12px'>{esc(p)}</li>" for p in pts)
    return (f"<div class='card' style='padding:30px 32px;display:flex;flex-direction:column'>"
            f"<div class='mono' style='font-size:18px;color:var(--accentd)'>{esc(j)}</div>"
            f"<div style='font:600 27px Geist;line-height:1.25;margin-top:14px'>{esc(title)}</div>"
            f"<div style='font-size:20px;color:var(--ink2);margin-top:12px'>{esc(au)}</div>"
            f"<div class='mono' style='font-size:16px;color:var(--muted);margin-top:8px'>{esc(doi)}</div>"
            f"<ul style='font-size:22px;line-height:1.38;margin-top:22px;padding-left:24px'>{li}</ul></div>")


page("s1_cards", f"""
<div class='pic' style='padding:52px 80px 0'>
  {section(1, 'The problem')}
  <h2 style='font-size:44px'>Models report high confidence while physical and chemical validity fail.</h2>
  <div style='display:grid;grid-template-columns:1.05fr 1.05fr 0.9fr;gap:28px;margin-top:38px'>
    {''.join(card(*c) for c in CARDS)}
  </div>
</div>""", "Sources verified 2026-10-18 via Europe PMC<br>full list: media/videos/video-c/REFERENCES.md")
shot("s1_cards", 16.0, [(0.5, "PoseBusters: deep-learning docking often returns physically implausible poses, and RMSD does not catch it."),
                        (6.2, "On 557 Mac1 complexes, the best confidence score reached ROC AUC 0.76 for poses within 2 Å."),
                        (11.8, "Runs N' Poses: co-folding methods largely memorise ligand poses.")])

# ---------------------------------------------------------------- 2 the old way
T3 = next(t for t in TILES if t["system"] == "cdk2" and t["run"] == 3)
CF = Path(next((RUN3 / "predictions/cdk2_pert/boltz2/seed_8").glob("boltz_results_*/predictions/*/confidence_*_model_0.json")))
keys = ["confidence_score", "ptm", "iptm", "ligand_iptm", "complex_plddt", "complex_iplddt"]
jl = "".join(f"<div>&#160;&#160;<span style='color:#9CC3E6'>\"{k}\"</span>: <span style='color:#E8C17A'>{CONF[k]:.3f}</span>,</div>" for k in keys)


def oldway(reveal: bool) -> str:
    over = ""
    if reveal:
        over = (f"<div style='position:absolute;left:24px;right:24px;bottom:24px;background:rgba(255,255,255,.95);border:2px solid var(--stop);"
                f"border-radius:8px;padding:20px 24px'>"
                f"<div style='font:600 26px Geist;color:var(--stop)'>What the score hides</div>"
                f"<div style='font-size:23px;line-height:1.5;margin-top:8px'>13 pocket residues cut to glycine (red spheres)<br>"
                f"crystal contacts recovered <span class='mono stop'>{FACTS3['key_interactions_recovered']} of {FACTS3['key_interactions_reference']}</span>"
                f" · buried polar atoms unpaired <span class='mono stop'>{FACTS3['buried_unsatisfied_polars']}</span></div></div>")
    verdict = ("<div style='font:600 30px Geist;color:var(--pass);margin-top:22px'>looks confident</div>" if not reveal else
               "<div style='font:600 30px Geist;color:var(--stop);margin-top:22px'>The score stays high. Nothing flags the failure.</div>")
    return f"""
<div class='pic' style='padding:52px 80px 0'>
  {section(2, 'The old way')}
  <h2 style='font-size:44px'>One input, one model, a structure and a confidence readout</h2>
  <div style='display:grid;grid-template-columns:1fr 0.95fr;gap:36px;margin-top:34px'>
    <div>
      <div style='background:#1F1F1C;border-radius:8px;padding:26px 30px;font:400 21px Geist Mono;color:#E6E6E1;line-height:1.5;height:500px'>
        <div style='color:#8B8B85'>$ boltz predict cdk2_pert.yaml --seed 8</div>
        <div style='color:#8B8B85'>$ cat {esc(CF.name)}</div>
        <div>{{</div>{jl}<div>&#160;&#160;…</div><div>}}</div>
      </div>
      {verdict}
    </div>
    <div class='card' style='position:relative;overflow:hidden;height:560px'>
      <img src='{file_url(TW / T3['png'])}' style='width:100%;height:100%;object-fit:cover'>
      <div style='position:absolute;left:0;top:0;background:rgba(255,255,255,.9);padding:8px 14px;font:600 22px Geist'>
        CDK2 1B38 · ATP · Boltz-2 seed 8</div>
      {over}
    </div>
  </div>
</div>"""


TAGOLD = ("bench run 3: predictions/cdk2_pert/boltz2/seed_8/…/" + CF.name + "<br>"
          "facts/cdk2_pert_boltz2.json · prep/cdk2_pert/meta.json")
page("s2_old_a", oldway(False), TAGOLD)
page("s2_old_b", oldway(True), TAGOLD)
shot("s2_old_a", 5.6, [(0.4, "The old way: CDK2 and ATP into Boltz-2. Back come a structure and ipTM 0.925.")])
shot("s2_old_b", 5.0, [(0.3, "The score stays high. Nothing flags the failure.")], xf=0.4, sfx="tick")

# ---------------------------------------------------------------- 3 with the harness: evidence map
GROUPS = [
    ("Provenance and identity", "L0", "var(--dock)", [("Sources resolved, with sha256", "UniProt, RCSB, PubChem"),
                                                     ("UniProt sequence vs SEQRES", "PDBe SIFTS"),
                                                     ("InChIKey vs CCD and PubChem", "RDKit")]),
    ("Input integrity", "L1–L2", "var(--dock)", [("Sequence, chains, truncations", "SIFTS range, gemmi"),
                                              ("Ligand identity and stereo", "RDKit"),
                                              ("Protonation at the stated pH", "PROPKA, Dimorphite-DL"),
                                              ("MSA depth, cofactors, pocket", "NumPy, fpocket")]),
    ("Applicability", "L3", "var(--accent)", [("Training-cutoff exposure", "RCSB search API"),
                                             ("Pocket similarity (SuCOS)", "RDKit"),
                                             ("Modality and token count", "models.yaml")]),
    ("Physical validity", "L4", "var(--pass)", [("PoseBusters: bonds, planarity, clashes, stereo", "RDKit"),
                                               ("Torsion strain", "RDKit MMFF94"),
                                               ("Minimisation drift", "OpenMM, AMBER14"),
                                               ("MolProbity", "Phenix, where installed")]),
    ("Chemical plausibility", "L4", "var(--pass)", [("Interaction fingerprint", "PLIP"),
                                                   ("Crystal contacts reproduced", "PLIP"),
                                                   ("Buried unsatisfied polar atoms", "FreeSASA"),
                                                   ("Hydrophobic complementarity", "FreeSASA")]),
    ("Stability", "L5", "var(--pass)", [("Independent seeds, spread", "spyrmsd"),
                                       ("Clusters and medoid", "spyrmsd"),
                                       ("Agreement across model families", "spyrmsd"),
                                       ("Pocket confidence per model", "models.yaml")]),
    ("Corroboration", "L5", "var(--pass)", [("Redocking control", "Vina"),
                                           ("RMSD to crystal", "spyrmsd"),
                                           ("Decoys and enrichment", "SciPy"),
                                           ("Perturbation response", "bench/")]),
]


def gcard(g: tuple) -> str:
    name, lay, col, items = g
    rows = "".join(f"<div style='padding:6px 0;border-top:1px solid var(--line2)'>"
                   f"<div>{esc(a)}</div><div class='mono' style='color:var(--accentd);font-size:16px;margin-top:2px'>{esc(b)}</div></div>"
                   for a, b in items)
    return (f"<div class='card' style='padding:16px 20px;border-top:5px solid {col}'>"
            f"<div style='display:flex;justify-content:space-between;align-items:baseline'><div style='font:600 23px Geist'>{name}</div>"
            f"<div class='mono' style='font-size:17px;color:{col}'>{lay}</div></div>"
            f"<div style='font-size:18px;margin-top:8px;line-height:1.3'>{rows}</div></div>")


page("s3_map", f"""
<div class='pic' style='padding:52px 70px 0'>
  {section(3, 'With the harness')}
  <div style='display:grid;grid-template-columns:330px 1fr;gap:34px;margin-top:6px'>
    <div>
      <div style='font:600 26px Geist;color:var(--ink2);line-height:1.3'>A model gives you</div>
      <div class='card' style='padding:24px 26px;margin-top:16px'>
        <div class='mono' style='font-size:34px;line-height:1.6'>pLDDT<br>ipTM</div>
        <div style='font-size:24px;color:var(--muted);margin-top:6px'>maybe a docking score</div>
      </div>
      <div style='font:600 26px Geist;color:var(--ink2);line-height:1.3;margin-top:44px'>The harness reports</div>
      <div style='font-size:22px;color:var(--ink2);margin-top:12px;line-height:1.45'>70 registered checks in layers 0 to 5. Each returns pass, warn, stop or skip, with its value, threshold and origin.</div>
    </div>
    <div style='display:grid;grid-template-columns:repeat(4,1fr);gap:16px;align-content:start'>
      {''.join(gcard(g) for g in GROUPS[:4])}
      <div style='grid-column:span 4;display:grid;grid-template-columns:repeat(3,1fr);gap:16px'>{''.join(gcard(g) for g in GROUPS[4:])}</div>
    </div>
  </div>
</div>""", "README.md check tables and Tools used<br>src/pah/checks/ (70 registered)")
shot("s3_map", 13.0, [(0.4, "With the harness, the same input runs through 70 checks in six layers."),
                      (4.6, "Each group names the tool that measures it: SIFTS, RDKit, PoseBusters, PLIP, OpenMM, spyrmsd."),
                      (9.4, "Each check returns a value, a threshold and its origin.")])

# verdict for the same CDK2 input
def issue_row(f: dict) -> str:
    g = f["gate"]
    msg = f["message"].replace(" in boltz2/seed8/sample0", "").replace(" for boltz2/seed8/sample0", "")
    if len(msg) > 92:
        msg = msg[:90].rsplit(" ", 1)[0] + " …"
    return (f"<div style='display:grid;grid-template-columns:110px 70px 470px 1fr;gap:18px;padding:19px 26px;border-bottom:1px solid var(--line2);align-items:center'>"
            f"<div class='{g}' style='font:500 21px Geist Mono'>{g}</div><div class='mono' style='font-size:19px;color:var(--muted)'>L{f['layer']}</div>"
            f"<div class='mono' style='font-size:19px'>{esc(f['check_id'])}</div><div style='font-size:20px;color:var(--ink2)'>{esc(msg)}</div></div>")


ISS = [FIND[c] for c in ["l2.context.cofactors", "l5.controls.redocking", "l4.interactions.unsatisfied_polars",
                         "l4.torsion_strain", "l5.agreement.cross_family", "l5.sampling.seeds"]]
v = REC["verdict"]
page("s3_verdict", f"""
<div class='pic' style='padding:52px 80px 0'>
  {section(3, 'With the harness')}
  <div style='display:flex;align-items:baseline;gap:26px'>
    <div style='font:600 52px Geist;color:var(--stop)'>stop</div>
    <div style='font-size:28px;color:var(--ink2)'>claim tested: “{esc(REC['claim'])}”</div>
  </div>
  <div class='mono' style='font-size:20px;color:var(--muted);margin-top:8px'>
    {sum(1 for f in REC['findings'] if f['gate']=='pass')} pass · {len(v['warnings'])} warn · {len(v['stops'])} stop · {len(v['incomplete'])} incomplete · {len(v['not_applicable'])} not applicable</div>
  <div class='card' style='margin-top:26px'>{''.join(issue_row(f) for f in ISS)}</div>
</div>""", "bench run 3: harness/cdk2_pert_boltz2/run/record.json")
shot("s3_verdict", 8.2, [(0.4, "Same CDK2 input: verdict stop, each issue with its measured value."),
                         (3.9, "Both stops are missing inputs: the Mg ion and a redocking control.")])

# ---------------------------------------------------------------- models
MODELS = [
    ("Co-folding", [("AlphaFold3", "output checks"), ("Boltz-1", "A100"), ("Boltz-2", "A100"), ("Chai-1", "A100"),
                    ("Protenix", "A100"), ("ColabFold (AlphaFold2)", "A100"), ("OpenFold3", "A100")]),
    ("Docking", [("DiffDock-L", "A100"), ("Gnina", "A100"), ("AutoDock Vina", "CPU")]),
    ("Protein–protein", [("HADDOCK3", "output checks"), ("pyDock", "output checks")]),
]
mrows = ""
for grp, items in MODELS:
    chips = "".join(f"<div class='card' style='padding:18px 22px;display:flex;justify-content:space-between;align-items:baseline'>"
                    f"<span style='font:600 27px Geist'>{esc(a)}</span><span class='mono' style='font-size:19px;color:{'var(--accentd)' if b == 'A100' else 'var(--muted)'}'>{esc(b)}</span></div>"
                    for a, b in items)
    mrows += (f"<div style='display:grid;grid-template-columns:260px 1fr;gap:24px;margin-top:26px;align-items:start'>"
              f"<div style='font:500 26px Geist;color:var(--ink2);padding-top:18px'>{grp}</div>"
              f"<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:14px'>{chips}</div></div>")
page("s4_models", f"""
<div class='pic' style='padding:52px 80px 0'>
  <div class='eyebrow'>Models it runs and checks</div>
  <h2 style='font-size:44px'>GPU tools on Modal A100, AutoDock Vina on CPU</h2>
  {mrows}
</div>""", "README.md, Tools used<br>configs/executors.yaml, configs/runtimes.yaml")
shot("s4_models", 8.4, [(0.4, "Boltz, Chai-1, Protenix, ColabFold, OpenFold3, DiffDock-L and Gnina run on Modal A100."),
                        (4.5, "Vina runs on CPU. AlphaFold3, HADDOCK3 and pyDock outputs are checked.")])

# ---------------------------------------------------------------- 4 input and output (live)
shot("UI_input", 0, [], kind="ui", xf=0.5)


def req_row(k: str, v_: str) -> str:
    return (f"<div style='display:grid;grid-template-columns:120px 1fr;padding:10px 0;border-top:1px solid var(--line2);font-size:22px'>"
            f"<div style='color:var(--muted)'>{k}</div><div>{v_}</div></div>")


LIVE_ISS = [("P1 STOP", "stop", "Redocking control reproduces the crystal pose", "control required by the task and not supplied", "L5"),
            ("P2 WARN", "warn", "Stereocentres and double-bond geometry defined", "undefined 1 · must be 0", "L1"),
            ("P2 WARN", "warn", "Receptor protonation at the stated pH", "pH 7.4 · pocket titratable 10 · ambiguous 2", "L2"),
            ("P2 WARN", "warn", "Ligand protonation and tautomers at the stated pH", "pH 7.4 · declared not enumerated 1", "L2")]
LIVE_ISSUES = "".join(
    f"<div style='display:grid;grid-template-columns:96px 1fr 50px;gap:14px;padding:10px 20px;border-bottom:1px solid var(--line2);align-items:baseline'>"
    f"<div class='mono {g}' style='font-size:17px'>{p_}</div><div><div style='font-size:20px'>{esc(t)}</div>"
    f"<div class='mono' style='font-size:16px;color:var(--ink2);margin-top:3px'>{esc(m)}</div></div>"
    f"<div class='mono' style='font-size:16px;color:var(--muted)'>{l_}</div></div>" for p_, g, t, m, l_ in LIVE_ISS)
page("s5_side", f"""
<div class='pic' style='padding:44px 70px 0'>
  {section(4, 'Input and output')}
  <div style='display:grid;grid-template-columns:560px 1fr;gap:40px'>
    <div>
      <div style='font:600 30px Geist'>Input</div>
      <div class='card' style='padding:8px 24px 12px;margin-top:14px'>
        {req_row('Target', 'Trypsin <span class="mono" style="color:var(--muted)">P00760</span>')}
        {req_row('Ligand', 'benzamidine <span class="mono" style="color:var(--muted)">BEN</span>')}
        {req_row('Tools', 'Boltz-2, Boltz-1, Chai-1, Protenix, Gnina, DiffDock-L, AutoDock Vina')}
        {req_row('Seeds', '<span class="mono">5</span>')}
      </div>
      <div class='card' style='margin-top:16px;overflow:hidden;position:relative;height:395px'>
        <img src='{file_url(LIVE / "3ptb_pocket.png")}' style='width:100%;height:100%;object-fit:cover'>
        <div style='position:absolute;left:0;top:0;background:rgba(255,255,255,.9);padding:6px 12px;font:600 20px Geist'>3PTB crystal, benzamidine pocket</div>
      </div>
    </div>
    <div>
      <div style='font:600 30px Geist'>Output <span class='mono' style='font-size:20px;color:var(--muted);font-weight:400'>ligand_pose-249098d10007 · 164 structures</span></div>
      <img src='{file_url(LIVE / "verdict.png")}' style='display:block;height:42px;margin-top:16px'>
      <div class='card' style='margin-top:12px'>{LIVE_ISSUES}</div>
      <div style='display:flex;gap:20px;margin-top:16px'>
        <img class='card' src='{file_url(LIVE / "structure.png")}' style='display:block;height:330px;width:420px;object-fit:cover;object-position:50% 62%'>
        <div style='font-size:22px;color:var(--ink2);line-height:1.5;padding-top:8px'>Boltz-2 medoid<br><span class='mono' style='font-size:18px'>boltz2/seed4/sample0<br>sha256 3b0642ef3822</span><br><br>PyMOL render from the run</div>
      </div>
    </div>
  </div>
</div>""", "live UI: /reports/ligand_pose-249098d10007<br>3PTB render: RCSB mmCIF, PyMOL")
shot("s5_side", 7.4, [(0.4, "The finished run: request and 3PTB crystal beside the verdict, its issues and the Boltz-2 medoid.")])

page("s5_exec", f"""
<div class='pic' style='padding:44px 70px 0'>
  {section(4, 'Input and output')}
  <div style='display:grid;grid-template-columns:930px 1fr;gap:36px'>
    <div>
      <div style='font:600 30px Geist'>Execution</div>
      <img class='card' src='{file_url(LIVE / "execution.png")}' style='display:block;width:100%;margin-top:14px;padding:8px;background:#fff'>
    </div>
    <div>
      <div style='font:600 30px Geist'>Ensemble</div>
      <div class='card' style='margin-top:14px;height:700px;overflow:hidden;position:relative'>
        <img src='{file_url(LIVE / "ensemble_top.png")}' style='position:absolute;left:-14px;top:-150px;width:1650px;display:block'></div>
    </div>
  </div>
</div>""", "live UI: /reports/ligand_pose-249098d10007 and /ensemble")
shot("s5_exec", 8.1, [(0.4, "Six tools ran on Modal A100, timed per seed. Vina ran on CPU."),
                      (4.45, "The Ensemble lists each structure with pLDDT, confidence and PoseBusters.")])
shot("UI_evidence", 0, [], kind="ui", xf=0.5)

# ---------------------------------------------------------------- 5 agents
shot("UI_agent", 0, [], kind="ui", xf=0.5)
a, b = STATS["A"], STATS["B"]
page("s6_agent", f"""
<div class='pic' style='padding:52px 80px 0'>
  {section(5, 'The AI agent result')}
  <h2 style='font-size:44px'>GLM-4.6, temperature 0, 3 repeats: confidence only vs the harness fact file</h2>
  <div style='display:grid;grid-template-columns:1fr 1fr 1.25fr;gap:28px;margin-top:90px'>
    <div class='card' style='padding:30px 34px'><div style='font-size:24px;color:var(--ink2)'>Balanced accuracy, run 3</div>
      <div style='display:flex;gap:40px;margin-top:14px;align-items:flex-end'>
        <div><div style='font-size:20px;color:var(--muted)'>score only</div><div class='mono stop' style='font-size:92px;line-height:1'>{a['balanced_accuracy']:.2f}</div></div>
        <div><div style='font-size:20px;color:var(--muted)'>fact file</div><div class='mono pass' style='font-size:92px;line-height:1'>{b['balanced_accuracy']:.2f}</div></div></div>
      <div style='font-size:21px;color:var(--ink2);margin-top:20px;line-height:1.5'>fact file 95% CI <span class='mono'>{b['ci95'][0]:.2f} to {b['ci95'][1]:.1f}</span><br>McNemar exact p <span class='mono'>{STATS['mcnemar']['p_exact']}</span> · 16 predictions</div></div>
    <div class='card' style='padding:30px 34px'><div style='font-size:24px;color:var(--ink2)'>Perturbed Boltz-2 poses rejected</div>
      <div style='display:flex;gap:40px;margin-top:14px;align-items:flex-end'>
        <div><div style='font-size:20px;color:var(--muted)'>score only</div><div class='mono stop' style='font-size:92px;line-height:1'>0/12</div></div>
        <div><div style='font-size:20px;color:var(--muted)'>fact file</div><div class='mono pass' style='font-size:92px;line-height:1'>12/12</div></div></div>
      <div style='font-size:21px;color:var(--ink2);margin-top:20px'>3 runs × 4 systems, majority of 3 repeats</div></div>
    <div class='card' style='padding:30px 34px;border-left:6px solid var(--warn)'><div style='font-size:24px;color:var(--ink2)'>Weakness</div>
      <div style='font-size:26px;line-height:1.45;margin-top:14px'>With the fact file the agent also rejected <span class='mono'>{b['fn']}</span> of <span class='mono'>{b['tp'] + b['fn']}</span> valid poses in run 3, two of them DiffDock-L poses within 2 Å of the crystal.</div></div>
  </div>
</div>""", "bench/runs/2026-10-17T1859Z-849c856/results/stats.json, report.md<br>bench/runs/*/results/decisions.csv")
shot("s6_agent", 12.4, [(0.4, "Run 3: balanced accuracy 0.50 vs 0.75 with the fact file, McNemar p 0.125."),
                        (5.2, "Over three runs: 12 of 12 perturbed Boltz-2 poses rejected, against 0 of 12."),
                        (9.6, "It also rejected valid DiffDock-L poses.")])

# ---------------------------------------------------------------- 6 files
ST = ROOT / "videos/public/stills"
FIG = CDK2 / "figures"


def fpanel(src: Path, label: str, fit: str = "cover", pos: str = "top") -> str:
    return (f"<div><img class='card' src='{file_url(src)}' style='display:block;width:100%;height:520px;object-fit:{fit};object-position:{pos};background:#fff'>"
            f"<div class='mono' style='font-size:20px;color:var(--ink2);margin-top:12px'>{label}</div></div>")


page("s7_files", f"""
<div class='pic' style='padding:52px 80px 0'>
  <div class='eyebrow'>Files every run writes</div>
  <h2 style='font-size:44px'>Report, provenance graph, PyMOL renders and figures, from the run record</h2>
  <div style='display:grid;grid-template-columns:1.25fr 1.25fr 0.9fr 0.9fr;gap:22px;margin-top:40px'>
    {fpanel(WORK / 'stills/report_shot.png', 'report.html', 'cover', 'left top')}
    {fpanel(WORK / 'stills/graph_tall.png', 'graph.json · .mmd · .svg', 'cover', 'center 8%')}
    {fpanel(ST / 'seed0-overview.png', 'renders/*.pse + .png')}
    {fpanel(FIG / 'posebusters_grid.png', 'figures/*.png · .svg · .csv', 'contain', 'center')}
  </div>
</div>""", "bench run 3: harness/cdk2_pert_boltz2/run/<br>render: run ui-vina (3PTB, Vina)")
shot("s7_files", 8.0, [(0.4, "Every run writes report.html, a provenance graph with sha256 checksums, PyMOL renders and figures.")])

page("s8_close", f"""
<div class='pic' style='display:flex;flex-direction:column;justify-content:center;padding-top:0;padding-left:160px'>
  <div style='margin-bottom:40px'>{logo(72)}</div>
  <div style='font-weight:600;font-size:80px;letter-spacing:-0.025em;line-height:1.12;max-width:1500px'>
    Every number traceable to a check, a tool and a <span style='color:var(--accent)'>source.</span></div>
  <div class='mono' style='font-size:34px;color:var(--ink2);margin-top:48px'>{SITE}</div>
  <div style='font-size:19px;color:var(--muted);margin-top:56px;max-width:1550px;line-height:1.5'>References: Buttenschoen et al., Chem. Sci. 2024, doi:10.1039/d3sc04185a ·
    Kim et al., eLife 2026, doi:10.7554/eLife.110475 · Škrinjar et al., Nat. Struct. Mol. Biol. 2026, doi:10.1038/s41594-026-01797-5</div>
</div>""", "Dock Harness · pah")
shot("s8_close", 6.0, [], sfx="whoosh")

page("zz_uiband", "", f"{SITE}<br>live web UI, recorded 2026-10-18")
(WORK / "shots.json").write_text(json.dumps(shots, indent=1))
print(len(shots), "shots;", sum(s["dur"] or 0 for s in shots), "s of stills before overlaps")
