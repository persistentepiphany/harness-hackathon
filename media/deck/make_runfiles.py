"""Compose run-output panels (provenance graph, PoseBusters grid, interactions) into one figure."""

import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt

out, *pairs = sys.argv[1:]
paths, titles = pairs[0::2], pairs[1::2]
imgs = [mpimg.imread(p) for p in paths]
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
