"""Render the 12 perturbed Boltz-2 predictions (4 systems x 3 bench runs) with PyMOL.

Usage: .venv/bin/python media/videos/video-c/render_twelve.py
Writes media/figures/twelve/<system>_run<k>.png, grid.png, twelve.json and README.md.

Structure per tile: the medoid pose named in that run's harness record (l5.sampling.clusters),
from bench/runs/<id>/predictions/<sys>_pert/boltz2/seed_<n>/. Each system has one camera: every
prediction is superposed by protein CA onto the run-3 prediction, and the view is framed on the
ligands of all three runs. Conventions follow bench/analysis/finding_panels.py: white background,
cartoon at 0.55 transparency, ligand sticks coloured by element, the residues cut to glycine marked
in #C4513B.
"""

from __future__ import annotations

import concurrent.futures as cf
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/user/harness-hackathon")
OUT = ROOT / "media/figures/twelve"
RUNS = ["2026-10-17T1611Z-426bfe9", "2026-10-17T1752Z-2f5a1c7", "2026-10-17T1859Z-849c856"]
SYSTEMS = [("cdk2", "CDK2", "1B38"), ("ftse", "FtsE", "8X61"), ("mek1", "MEK1", "7XLP"),
           ("glc", "glucose dehydrogenase", "2VWH")]
W, H = 960, 720

SCRIPT = r"""
import json, os, sys
from pymol import cmd
a = json.loads(sys.argv[1])
cmd.reinitialize()
cmd.set("ray_opaque_background", 1)
cmd.bg_color("white")
cmd.set("ray_shadows", 0)
cmd.set("antialias", 2)
cmd.set("cartoon_transparency", 0.55)
cmd.set("stick_radius", 0.26)
cmd.set("sphere_scale", 0.45)
cmd.set("depth_cue", 1)
cmd.set("max_threads", 2)
cmd.load(a["ref"], "ref")
for i, p in enumerate(a["all"]):
    cmd.load(p, f"o{i}")
    cmd.align(f"o{i} and polymer and name CA", "ref and polymer and name CA")
cmd.load(a["pose"], "m")
cmd.align("m and polymer and name CA", "ref and polymer and name CA")
cmd.remove("hydro")
cmd.hide("everything")
lig = "m and chain L"
cmd.show("cartoon", "m and polymer")
cmd.color("0xC7D8CC", "m and polymer")
pocket = "byres (m and polymer and not name N+C+O) within 4.5 of (" + lig + ")"
cmd.show("sticks", pocket + " and sidechain")
cmd.set("stick_radius", 0.14, "m and polymer")
cmd.color("0x9A9A92", pocket + " and elem C")
cmd.util.cnc(pocket)
cofac = "m and not polymer and not chain L and not solvent"
cmd.show("sticks", cofac)
cmd.show("spheres", cofac + " and inorganic")
cmd.color("0x8FA9C7", cofac + " and elem C")
if a["cut"]:
    sel = "m and polymer and name CA and resi " + "+".join(a["cut"])
    cmd.show("spheres", sel)
    cmd.color("0xC4513B", sel)
cmd.show("sticks", lig)
cmd.color("0xB07E2C", lig + " and elem C")
cmd.util.cnc(lig)
cmd.orient("ref and chain L")
cmd.zoom(" or ".join(f"(o{i} and chain L)" for i in range(len(a["all"]))) + " or (ref and chain L)", a["pad"])
cmd.disable("ref")
for i in range(len(a["all"])):
    cmd.disable(f"o{i}")
cmd.png(a["out"], width=a["w"], height=a["h"], dpi=150, ray=1)
"""


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def medoid_seed(run: Path, key: str) -> tuple[int, str]:
    rec = json.loads((run / "harness" / f"{key}_pert_boltz2" / "run" / "record.json").read_text())
    for f in rec["findings"]:
        if f["check_id"] == "l5.sampling.clusters":
            med = f.get("evidence", {}).get("medoid") or f["message"].split("medoid ")[1].split(";")[0]
            return int(med.split("/")[1].removeprefix("seed")), "record.json l5.sampling.clusters"
    seeds = sorted((run / "predictions" / f"{key}_pert" / "boltz2").glob("seed_*"))
    return int(seeds[0].name.split("_")[1]), "first seed (no medoid in record)"


def complex_path(run: Path, key: str, seed: int) -> Path:
    hits = sorted((run / "predictions" / f"{key}_pert" / "boltz2" / f"seed_{seed}").glob(
        "boltz_results_*/predictions/*/*_model_0.cif"))
    if not hits:
        raise SystemExit(f"no complex for {run.name} {key} seed {seed}")
    return hits[0]


def majority(rows: list[dict], arm: str) -> tuple[str, list[str]]:
    v = [r["verdict"] for r in rows if r["arm"] == arm]
    return max(set(v), key=v.count), v


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tiles = []
    for k, rid in enumerate(RUNS, 1):
        run = ROOT / "bench/runs" / rid
        dec = list(csv.DictReader(open(run / "results/decisions.csv")))
        truth = {(r["system"], r["executor"]): r for r in csv.DictReader(open(run / "results/truth.csv"))}
        for key, label, pdb in SYSTEMS:
            seed, seed_src = medoid_seed(run, key)
            pose = complex_path(run, key, seed)
            facts = json.loads((run / "facts" / f"{key}_pert_boltz2.json").read_text())
            meta = json.loads((run / "prep" / f"{key}_pert" / "meta.json").read_text())
            rows = [r for r in dec if r["system"] == f"{key}_pert" and r["executor"] == "boltz2"]
            a_maj, a_votes = majority(rows, "A")
            b_maj, b_votes = majority(rows, "B")
            b_reason = next(r["reason"] for r in rows if r["arm"] == "B" and r["verdict"] == b_maj)
            tiles.append({
                "system": key, "label": label, "pdb": pdb, "run": k, "run_id": rid, "seed": seed,
                "seed_source": seed_src, "structure": str(pose.relative_to(ROOT)), "sha256": sha(pose),
                "png": f"{key}_run{k}.png",
                "perturbation": meta["perturbation"], "cut_to_gly": [m["residue"] for m in meta["mutations"]],
                "cut_idx": [str(m["seqres_index"]) for m in meta["mutations"]],
                "confidence": facts["confidence"], "posebusters": facts["posebusters"],
                "contacts_recovered": facts["key_interactions_recovered"],
                "contacts_reference": facts["key_interactions_reference"],
                "buried_unsatisfied_polars": facts["buried_unsatisfied_polars"],
                "torsion_strain_kcal": facts["torsion_strain_kcal"],
                "cross_tool_rmsd_A": facts["cross_tool_rmsd_A"],
                "truth": truth[(f"{key}_pert", "boltz2")]["truth"],
                "arm_A": a_maj, "arm_A_votes": a_votes, "arm_B": b_maj, "arm_B_votes": b_votes,
                "arm_B_reason_example": b_reason,
            })
    by_sys: dict[str, list[dict]] = {}
    for t in tiles:
        by_sys.setdefault(t["system"], []).append(t)
    jobs = []
    for key, ts in by_sys.items():
        ref = next(t for t in ts if t["run"] == 3)
        for t in ts:
            jobs.append({"ref": str(ROOT / ref["structure"]), "all": [str(ROOT / x["structure"]) for x in ts],
                         "pose": str(ROOT / t["structure"]), "cut": t["cut_idx"], "pad": 6.0,
                         "out": str(OUT / t["png"]), "w": W, "h": H})

    def go(j: dict) -> str:
        p = subprocess.run([sys.executable, "-c", SCRIPT, json.dumps(j)], capture_output=True, text=True,
                           timeout=900)
        if p.returncode:
            raise SystemExit((p.stderr or p.stdout)[-2000:])
        return j["out"]

    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for o in ex.map(go, jobs):
            print("rendered", Path(o).name)
    for t in tiles:
        t["png_sha256"] = sha(OUT / t["png"])
    (OUT / "twelve.json").write_text(json.dumps(tiles, indent=1))
    grid(tiles)


def grid_only() -> None:
    grid(json.loads((OUT / "twelve.json").read_text()))


def grid(tiles: list[dict]) -> None:
    from PIL import Image, ImageDraw, ImageFont

    fdir = Path("/home/user/harness-hackathon/out/videos/c/fonts")
    f1 = ImageFont.truetype(str(fdir / "Geist-Medium.ttf"), 26)
    f2 = ImageFont.truetype(str(fdir / "GeistMono-Regular.ttf"), 21)
    tw, th, lab, gap = 480, 360, 74, 12
    order = [k for k, *_ in SYSTEMS]
    img = Image.new("RGB", (4 * tw + 5 * gap, 3 * (th + lab) + 4 * gap), "#F7F7F4")
    d = ImageDraw.Draw(img)
    for t in tiles:
        c, r = order.index(t["system"]), t["run"] - 1
        x, y = gap + c * (tw + gap), gap + r * (th + lab + gap)
        im = Image.open(OUT / t["png"]).convert("RGB").resize((tw, th), Image.LANCZOS)
        img.paste(im, (x, y))
        lbl = "glucose DH" if t["system"] == "glc" else t["label"]
        d.text((x + 6, y + th + 8), f"{lbl} {t['pdb']} · run {t['run']} · seed {t['seed']}", fill="#1A1A18", font=f1)
        c_ = t["confidence"]
        d.text((x + 6, y + th + 44), f"ipTM {c_['ligand_iptm']:.3f}  pocket pLDDT {c_['pocket_plddt']:.1f}",
               fill="#55554F", font=f2)
    img.save(OUT / "grid.png")
    print("grid", img.size)


if __name__ == "__main__":
    grid_only() if "--grid" in sys.argv else main()
