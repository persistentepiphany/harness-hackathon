"""Renders one structure with PyMOL in its own process. Invoked by `pah.report.renders`.

    python -m pah.report.pymol_worker '<json request>'

Prints one JSON object: {"pngs": {...}, "pse": str, "organic": [...], "chains": [...]}.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

CHAIN_COLOURS = ("palegreen", "lightblue", "lightpink", "wheat", "palecyan", "lightorange")


def render(req: dict[str, Any]) -> dict[str, Any]:
    from pymol import cmd, util

    cmd.feedback("disable", "all", "everything")
    cmd.reinitialize()
    cmd.load(req["structure"], "target")
    for i, lig in enumerate(req.get("ligands", [])):
        cmd.load(lig, f"input_ligand_{i}")
    cmd.remove("solvent")
    cmd.hide("everything")
    cmd.show("cartoon", "polymer")
    for i, chain in enumerate(cmd.get_chains("target")):
        cmd.color(CHAIN_COLOURS[i % len(CHAIN_COLOURS)], f"target and chain {chain} and polymer")
    organic = "organic and target"
    cmd.show("sticks", organic)
    util.cbao(organic)
    cmd.set("stick_radius", 0.25)
    cmd.show("spheres", "inorganic and target")
    cmd.set("sphere_scale", 0.35)
    if req.get("ligands"):
        cmd.show("sticks", "input_ligand_*")
        util.cbam("input_ligand_*")
    cmd.bg_color("white")
    for key, value in (("ray_opaque_background", 1), ("antialias", 1), ("ray_shadows", 0)):
        cmd.set(key, value)
    width, height = int(req.get("width", 960)), int(req.get("height", 720))
    names: set[str] = set()
    cmd.iterate(organic, "names.add(resn)", space={"names": names})
    chains = sorted(cmd.get_chains("target"))
    out: dict[str, Any] = {"pngs": {}, "organic": sorted(names), "chains": chains}
    stem = Path(req["out_stem"])
    cmd.orient("target")
    cmd.zoom("polymer or organic", 3)
    cmd.show("spheres", organic)
    overview = f"{stem}_overview.png"
    cmd.png(overview, width=width, height=height, dpi=150, ray=1)
    out["pngs"]["overview"] = overview
    cmd.hide("spheres", organic)
    if cmd.count_atoms(organic):
        pocket_sel = f"byres (polymer within 5 of ({organic}))"
        cmd.show("lines", pocket_sel)
        cmd.color("grey50", f"({pocket_sel}) and elem C")
        cmd.orient(organic)
        cmd.zoom(organic, 7)
        pocket = f"{stem}_pocket.png"
        cmd.png(pocket, width=width, height=height, dpi=150, ray=1)
        out["pngs"]["pocket"] = pocket
    out["pse"] = f"{stem}.pse"
    cmd.save(out["pse"])
    return out


if __name__ == "__main__":
    sys.stdout.write(json.dumps(render(json.loads(sys.argv[1]))) + "\n")
