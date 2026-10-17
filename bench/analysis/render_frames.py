"""Walkthrough video of one benchmark run, built only from its recorded files.

    python bench/analysis/render_frames.py --run-id <id> [--system cdk2] [--executor boltz2]

Scenes, timed by .claude/skills/human-pace (title cards 2.5 s, reading holds of 0.3 s per word,
final hold 2 s):
  1. the question
  2. the design (four systems, two states, two executors, two agent arms)
  3. the wild-type prediction, turning, ligand highlighted
  4. the perturbed prediction in the same orientation, glycine positions highlighted
  5. the same prediction as each arm saw it (score only, then the fact file)
  6. balanced accuracy and confusion matrices from results/figures
  7. the limits of the result
Frames are 1280x720 PNGs in <run>/video/frames; the film is <run>/results/walkthrough.mp4.
PyMOL renders run in a subprocess so a PyMOL failure cannot stop the build.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
W, H, FPS = 1280, 720, 30
INK, INK2, MUTED, CANVAS, LINE = "#1A1A18", "#55554F", "#8B8B85", "#F7F7F4", "#E6E6E1"
ACCENT, PASS, STOP = "#B07E2C", "#3B8A58", "#C4513B"

PYMOL_SCRIPT = r"""
import json, os, sys
from pymol import cmd
a = json.loads(sys.argv[1])
cmd.reinitialize()
cmd.set("ray_opaque_background", 1)
cmd.bg_color("white")
cmd.load(a["structure"], "target")
cmd.remove("hydro")
cmd.hide("everything")
cmd.show("cartoon", "polymer")
cmd.color("0xA8CBB0", "polymer")
cmd.set("cartoon_transparency", 0.15)
lig = "target and not polymer and not solvent and not inorganic"
if a.get("ligand"):
    cmd.load(a["ligand"], "lig")
    lig = "lig"
cmd.show("sticks", lig)
cmd.color("0xB07E2C", lig + " and elem C")
cmd.util.cnc(lig)
cmd.set("stick_radius", 0.28)
near = "byres (polymer within 5 of " + lig + ")"
cmd.show("sticks", near + " and not name N+C+O")
cmd.color("0x55554F", near + " and elem C")
for sel in a.get("highlight", []):
    s = "polymer and resi " + sel
    cmd.show("sticks", s + " and name CA")
    cmd.show("spheres", s + " and name CA")
    cmd.set("sphere_scale", 0.55, s)
    cmd.color("0xC4513B", s + " and name CA")
cmd.orient(lig)
cmd.zoom(lig, 9)
cmd.set("ray_shadows", 0)
cmd.set("antialias", 2)
cmd.set("max_threads", os.cpu_count() or 1)
n = int(a["frames"])
for i in range(n):
    cmd.turn("y", 360.0 / n)
    cmd.png(a["out"] % i, width=a["w"], height=a["h"], dpi=150, ray=1)
"""


def _font(size: int, mono: bool = False) -> Any:
    from PIL import ImageFont

    names = (["DejaVuSansMono.ttf"] if mono else []) + ["DejaVuSans.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _canvas() -> Any:
    from PIL import Image

    return Image.new("RGB", (W, H), CANVAS)


def card(lines: list[tuple[str, int, str, bool]], eyebrow: str = "") -> Any:
    """Text card: (text, size, colour, mono) per line, left aligned on the canvas."""
    from PIL import ImageDraw

    img = _canvas()
    d = ImageDraw.Draw(img)
    y = 150
    if eyebrow:
        d.text((110, y - 50), eyebrow.upper(), fill=MUTED, font=_font(16))
    for text, size, colour, mono in lines:
        for row in textwrap.wrap(text, width=max(20, int(1900 / size))) or [""]:
            d.text((110, y), row, fill=colour, font=_font(size, mono))
            y += int(size * 1.45)
        y += 10
    return img


def hold(text: str, minimum: float = 1.5) -> float:
    return max(minimum, 0.3 * len(text.split()))


class Film:
    def __init__(self, frames: Path) -> None:
        self.frames = frames
        self.n = 0

    def add(self, img: Any, seconds: float) -> None:
        path = self.frames / f"{self.n:05d}.png"
        img.save(path)
        for _ in range(max(1, round(seconds * FPS)) - 1):
            self.n += 1
            shutil.copyfile(path, self.frames / f"{self.n:05d}.png")
        self.n += 1

    def add_sequence(self, images: list[Any]) -> None:
        for img in images:
            img.save(self.frames / f"{self.n:05d}.png")
            self.n += 1


def render_turn(structure: Path, ligand: Path | None, highlight: list[str], out: Path,
                frames: int) -> list[Path]:  # fmt: skip
    out.mkdir(parents=True, exist_ok=True)
    args = {"structure": str(structure), "ligand": str(ligand) if ligand else None,
            "highlight": highlight, "frames": frames, "out": str(out / "f%04d.png"),
            "w": 760, "h": 600}  # fmt: skip
    stamp = out / "turn.json"
    done = sorted(out.glob("f*.png"))
    if stamp.is_file() and json.loads(stamp.read_text()) == args and len(done) == frames:
        return done
    for old in done:
        old.unlink()
    subprocess.run([sys.executable, "-c", PYMOL_SCRIPT, json.dumps(args)], check=True,
                   timeout=3600, capture_output=True)  # fmt: skip
    stamp.write_text(json.dumps(args))
    return sorted(out.glob("f*.png"))


def structure_frame(render: Path, title: str, rows: list[tuple[str, str]], tag: str,
                    tag_colour: str) -> Any:  # fmt: skip
    from PIL import Image, ImageDraw

    img = _canvas()
    pic = Image.open(render).convert("RGB")
    img.paste(pic, (40, 60))
    d = ImageDraw.Draw(img)
    x = 840
    avail = W - x - 40
    d.text((x, 70), tag.upper(), fill=tag_colour, font=_font(18))
    d.text((x, 100), title, fill=INK, font=_font(28))
    y = 160
    vf = _font(20, mono=True)
    for label, value in rows:
        d.text((x, y), label.upper(), fill=MUTED, font=_font(14))
        y += 22
        for line in _wrap_px(d, value, vf, avail):
            d.text((x, y), line, fill=INK, font=vf)
            y += 26
        y += 14
    return img


def _wrap_px(draw: Any, text: str, font: Any, width: int) -> list[str]:
    """Greedy word wrap to a pixel width, so long values do not run past the panel edge."""
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if cur and draw.textlength(trial, font=font) > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines or [""]


def text_panel(title: str, body: str, eyebrow: str) -> Any:
    from PIL import ImageDraw

    img = _canvas()
    d = ImageDraw.Draw(img)
    d.text((80, 50), eyebrow.upper(), fill=MUTED, font=_font(16))
    d.text((80, 80), title, fill=INK, font=_font(28))
    y = 140
    for line in body.splitlines():
        for row in textwrap.wrap(line, width=96) or [""]:
            d.text((80, y), row, fill=INK2, font=_font(15, mono=True))
            y += 21
    return img


def figure_frame(png: Path, title: str, caption: str) -> Any:
    from PIL import Image, ImageDraw

    img = _canvas()
    d = ImageDraw.Draw(img)
    d.text((80, 40), title, fill=INK, font=_font(28))
    fig = Image.open(png).convert("RGB")
    fig.thumbnail((W - 160, H - 190))
    img.paste(fig, ((W - fig.width) // 2, 100))
    d.text((80, H - 60), caption, fill=INK2, font=_font(18))
    return img


def main() -> None:
    sys.path.insert(0, str(REPO / "bench" / "agent"))
    from decide import prompt

    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--system", default="cdk2")
    ap.add_argument("--executor", default="boltz2")
    args = ap.parse_args()
    run = REPO / "bench" / "runs" / args.run_id
    stats = json.loads((run / "results" / "stats.json").read_text())
    work = run / "video"
    frames = work / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True)
    film = Film(frames)

    q = (
        "Does an agent given the harness fact file tell valid from invalid poses better than "
        "the same agent given only the model's confidence score?"
    )
    film.add(card([(q, 34, INK, False)], "Perturbation benchmark"), 2.5 + hold(q))
    design = (
        "Four systems (FtsE, CDK2, MEK1, glucose dehydrogenase), each wild type and "
        "perturbed. Boltz-2 and DiffDock-L, three seeds each. Every prediction judged "
        "twice by GLM: score only, then the harness fact file."
    )
    film.add(card([(design, 26, INK2, False)], "Design"), hold(design))

    facts = {}
    for state in ("wt", "pert"):
        name = f"{args.system}_{state}_{args.executor}"
        facts[state] = json.loads((run / "facts" / f"{name}.json").read_text())
    for state in ("wt", "pert"):
        f = facts[state]
        meta = json.loads((run / "prep" / f"{args.system}_{state}" / "meta.json").read_text())
        harness = run / "harness" / f"{args.system}_{state}_{args.executor}" / "run"
        rep = f["representative_pose"]
        pose_dir = next(harness.glob(f"predictions/*/{rep}"), None)
        ligand = pose_dir / "ligand.sdf" if pose_dir else None
        structure = next((pose_dir.glob("complex*")), None) if pose_dir else None
        if structure is None:
            record = json.loads((harness / "record.json").read_text())
            structure = Path(next(a["path"] for a in record["artifacts"]
                                  if a["label"] == rep))  # fmt: skip
        highlight = [str(m["seqres_index"]) for m in meta["mutations"]] if args.executor == \
            "boltz2" else [m["residue"][3:] for m in meta["mutations"]]  # fmt: skip
        renders = render_turn(structure, ligand, highlight, work / f"turn_{state}", 150)
        conf = facts[state]["confidence"]
        rows = [("confidence", ", ".join(f"{k} {v}" for k, v in conf.items() if v is not None)),
                ("PoseBusters", f"{f['posebusters']['passed']} of {f['posebusters']['total']}"),
                ("deposited interactions recovered",
                 f"{f['key_interactions_recovered']} of {f['key_interactions_reference']}"),
                ("buried unsatisfied polars", str(f["buried_unsatisfied_polars"])),
                ("mutations", str(len(meta["mutations"]))
                 + (f", {len(meta['methylated_oxygens'])} hydroxyls methylated"
                    if meta["methylated_oxygens"] else ""))]  # fmt: skip
        tag = "wild type" if state == "wt" else "perturbed"
        title = f"{meta['protein']} · {meta['ligand_code']}"
        film.add_sequence(
            [structure_frame(r, title, rows, tag, PASS if state == "wt" else STOP) for r in renders]
        )

    pa = prompt("A", facts["pert"])
    pb = prompt("B", facts["pert"])
    film.add(text_panel("What the score-only arm sees", pa, "perturbed prediction"), hold(pa, 4))
    film.add(text_panel("What the fact-file arm sees", pb, "perturbed prediction"), 9.0)

    figs = run / "results" / "figures"
    allb = stats["arms"]["all"]
    cap = (
        f"Pooled balanced accuracy: score only {allb['A']['balanced_accuracy']}, fact file "
        f"{allb['B']['balanced_accuracy']}; McNemar exact p {allb['mcnemar']['p_exact']}"
    )
    film.add(figure_frame(figs / "balanced_accuracy.png", "Balanced accuracy", cap), hold(cap, 6))
    film.add(
        figure_frame(
            figs / "confusion.png",
            "Confusion matrices, pooled",
            f"{allb['n']} predictions with ground truth",
        ),
        6.0,
    )
    limits = (
        "Eight systems support a demonstration, not a statistical claim. Perturbed systems "
        "are negatives by construction. The arms differ in prompt length as well as "
        "content."
    )
    film.add(card([(limits, 26, INK2, False)], "What this does not establish"), hold(limits) + 2)
    out = run / "results" / "walkthrough.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i",
                    str(frames / "%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "20", str(out)], check=True)  # fmt: skip
    print(f"{out} ({film.n / FPS:.1f} s, {film.n} frames)")


if __name__ == "__main__":
    main()
