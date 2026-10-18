"""Compose image panels side by side with titles (run outputs, PyMOL renders) into one figure.

Usage: make_runfiles.py OUT IMG TITLE [IMG TITLE ...]; env WS (wspace), FS (title pt),
TRIM (crop white margins, keeping TRIM pixels).
"""

import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt

out, *pairs = sys.argv[1:]
paths, titles = pairs[0::2], pairs[1::2]
imgs = [mpimg.imread(p) for p in paths]
if os.environ.get("TRIM"):
    # crop uniform white margins, keeping a small border
    pad = int(os.environ.get("TRIM"))
    trimmed = []
    for im in imgs:
        rgb = im[..., :3]
        mask = (rgb < 0.97).any(axis=2)
        rows, cols = mask.any(axis=1).nonzero()[0], mask.any(axis=0).nonzero()[0]
        r0, r1 = max(rows[0] - pad, 0), min(rows[-1] + pad, im.shape[0])
        c0, c1 = max(cols[0] - pad, 0), min(cols[-1] + pad, im.shape[1])
        trimmed.append(im[r0:r1, c0:c1])
    imgs = trimmed
ratios = [im.shape[1] / im.shape[0] for im in imgs]
wspace = float(os.environ.get("WS", "0.04"))
fontsize = float(os.environ.get("FS", "13"))
fig, axes = plt.subplots(
    1,
    len(imgs),
    figsize=(sum(ratios) * 4.2, 4.9),
    dpi=220,
    gridspec_kw={"width_ratios": ratios, "wspace": wspace},
)
for ax, im, t in zip(axes, imgs, titles, strict=False):
    ax.imshow(im)
    ax.set_title(t, fontsize=fontsize, loc="left", color="#1F2328")
    ax.axis("off")
fig.savefig(out, bbox_inches="tight", pad_inches=0.05, facecolor="white")
