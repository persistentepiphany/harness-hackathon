"""PyMOL panels for the finding deck: where the ligand went when the pocket was cut away.

    python bench/analysis/finding_panels.py --run-id <id>

For each target it superposes the perturbed prediction onto the wild-type prediction by protein
backbone, fixes one camera, and renders both states through it. A shared camera is the point: the
per-run renders orient on the ligand, which hides a ligand that has moved. Writes PNGs to
<run>/finding/panels/.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]

# Rendered through one camera per target, so the two panels are comparable.
PYMOL_SCRIPT = r"""
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
cmd.set("sphere_scale", 0.5)
cmd.set("max_threads", os.cpu_count() or 1)

cmd.load(a["wt"], "wt")
cmd.load(a["pert"], "pert")
cmd.remove("hydro")
# Superpose on the protein only, so any ligand movement is real and not an alignment artefact.
cmd.align("pert and polymer and name CA", "wt and polymer and name CA")

for obj in ("wt", "pert"):
    cmd.hide("everything", obj)
    cmd.show("cartoon", obj + " and polymer")
    cmd.color("0xC7D8CC", obj + " and polymer")
    lig = obj + " and not polymer and not solvent"
    cmd.show("sticks", lig)
    cmd.color(a["colour"][obj], lig + " and elem C")
    cmd.util.cnc(lig)

# The pocket residues that were cut to glycine, marked on the wild-type copy.
if a["highlight"]:
    sel = "wt and polymer and resi " + "+".join(a["highlight"])
    cmd.show("sticks", sel + " and sidechain")
    cmd.color("0xC4513B", sel + " and elem C")

# One camera for both panels: framed on everything that matters in either state.
cmd.orient("wt and not polymer and not solvent")
cmd.zoom("(wt or pert) and not polymer and not solvent", float(a["pad"]))
view = cmd.get_view()

for name, out in (("wt", a["out_wt"]), ("pert", a["out_pert"])):
    cmd.disable("wt")
    cmd.disable("pert")
    cmd.enable(name)
    if a["highlight"] and name == "pert":
        cmd.enable("wt")
        cmd.hide("everything", "wt")
        sel = "wt and polymer and resi " + "+".join(a["highlight"])
        cmd.show("sticks", sel + " and sidechain")
    cmd.set_view(view)
    cmd.png(out, width=a["w"], height=a["h"], dpi=150, ray=1)
"""

TARGETS = {
    "ftse": {"seed": 7, "pad": 6.0, "label": "FtsE"},
    "cdk2": {"seed": 8, "pad": 5.0, "label": "CDK2"},
}


def complex_path(run: Path, system: str, state: str, seed: int) -> Path:
    hits = sorted(
        (run / "predictions" / f"{system}_{state}" / "boltz2" / f"seed_{seed}").glob(
            "boltz_results_*/predictions/*/*_model_0.cif"
        )
    )
    if not hits:
        raise SystemExit(f"no predicted complex for {system}_{state} seed {seed}")
    return hits[0]


def render(run: Path, system: str, spec: dict[str, Any], out: Path) -> dict[str, Path]:
    meta = json.loads((run / "prep" / f"{system}_pert" / "meta.json").read_text())
    args = {
        "wt": str(complex_path(run, system, "wt", spec["seed"])),
        "pert": str(complex_path(run, system, "pert", spec["seed"])),
        # Boltz renumbers to the sequence, so the mutated positions are seqres indices.
        "highlight": [str(m["seqres_index"]) for m in meta["mutations"]],
        "colour": {"wt": "0x3B8A58", "pert": "0xC4513B"},
        "pad": spec["pad"],
        "out_wt": str(out / f"{system}_wt.png"),
        "out_pert": str(out / f"{system}_pert.png"),
        "w": 1100,
        "h": 900,
    }
    out.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "-c", PYMOL_SCRIPT, json.dumps(args)],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if proc.returncode:
        raise SystemExit((proc.stderr or proc.stdout)[-2000:])
    return {"wt": Path(args["out_wt"]), "pert": Path(args["out_pert"])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    run = REPO / "bench" / "runs" / args.run_id
    out = run / "finding" / "panels"
    for system, spec in TARGETS.items():
        paths = render(run, system, spec, out)
        print(f"{system}: {paths['wt'].name}, {paths['pert'].name}")


if __name__ == "__main__":
    main()
