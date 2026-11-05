"""Turns the plain grey backdrop of a ChatGPT concept render (connected to the image border) white,
so the unit/building pipelines (which key out white) can use it.
  python3 artsrc/space/whiten_bg.py in.png out.png [tolerance]
"""
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, label

src, dst = sys.argv[1], sys.argv[2]
tol = float(sys.argv[3]) if len(sys.argv) > 3 else 60
a = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)
h, w, _ = a.shape
border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
bg_col = np.median(border, axis=0)
# backdrop = low-saturation pixels close to the backdrop grey (allows a soft vertical gradient)
dist = np.abs(a - bg_col).max(-1)
grey = (a.max(-1) - a.min(-1)) < 10
labels, _ = label((dist < tol) & grey)
edge_ids = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
bg = np.isin(labels, edge_ids[edge_ids > 0])
out = a.copy()
out[bg] = 255
# blend a 1px rim so the cut is not jagged
rim = binary_dilation(bg, iterations=1) & ~bg
out[rim] = (a[rim] + 255) / 2
Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(dst)
print(dst, "bg", bg_col.round(), f"{bg.mean():.0%} backdrop")
