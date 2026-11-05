#!/usr/bin/env python3
"""
Builds the HD foundation pads drawn under the HD buildings by WithPxBuildingPad.

The HD building renders are seen from the front-left corner, so a grid-aligned bib looks like a
sheet of paper under them. Instead, each building's base is measured from its sprite and the pad
art in src/ is warped onto that base (plus an apron in front of it):

- The lower outline of the sprite is fitted with two lines; their meeting point is the front corner C
  and the first line is the front edge (L -> C, falling to the right). All renders share roughly one
  camera, so the right edge uses a fixed screen angle (RIGHT_EDGE_DEG) rather than a fit, which walls
  and cranes throw off. OVERRIDES fixes buildings the fit gets wrong.
- The pad's bottom edge (hazard stripe) is mapped to the front edge pushed forward by APRON.
- The pad canvas is the building canvas grown evenly on each side, so with the building's own
  sequence Offset and Scale it lines up exactly with the building.

Writes mods/rapx/bits/hd/pads/<id>-<terrain>.png and mods/rapx/sequences/hd-bibs.yaml.

  python3 artsrc/bibs/make_bibs.py [--debug]    (--debug writes previews to artsrc/bibs/preview/)
"""
import math
import os
import re
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(HERE, "src")
HD = os.path.join(ROOT, "mods", "rapx", "bits", "hd")
OUT = os.path.join(HD, "pads")
YAML = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-bibs.yaml")
HD_SEQUENCES = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-structures.yaml")

sys.path.insert(0, os.path.join(HERE, "..", "buildings"))
from build_all import BUILDINGS, DENSITY, TILESETS  # noqa: E402

# Which source art each tileset uses.
TERRAIN = {"TEMPERAT": "temperate", "SNOW": "snow", "DESERT": "temperate", "INTERIOR": "temperate"}

# Buildings that get a pad (those that had the stock full-size bib).
PADDED = ["fact", "proc", "apwr", "stek", "weap", "powr", "barr", "tent", "dome", "atek", "hpad"]

RIGHT_EDGE_DEG = 45   # screen angle of the base's right edge, rising to the right
DEPTH = 0.8           # base depth along the right edge, as a fraction of the front edge
APRON = 0.16          # pad extends in front of the building, as a fraction of the sprite width
SIDE = 0.07           # and beyond its left and right corners, as a fraction of the front edge
SUPERSAMPLE = 4

# id: {"L": (x, y), "C": (x, y)} in sprite pixels, replacing the fitted corners.
OVERRIDES = {}


def building_offset(bid):
	"""The idle sequence Offset of an HD building, from hd-structures.yaml."""
	text = open(HD_SEQUENCES).read()
	block = re.search(rf"^{bid}:\n\tidle:\n(?:\t\t.*\n)*?\t\tOffset: (-?\d+),(-?\d+)", text, re.M)
	return int(block.group(1)), int(block.group(2))


def fit_base(img):
	"""Returns the base's left corner L and front corner C (sprite pixels)."""
	a = np.asarray(img).astype(int)
	solid = (a[..., 3] > 200) & (a[..., :3].max(-1) > 45)    # building without its cast shadow
	env = np.array([(x, np.nonzero(solid[:, x])[0].max()) for x in range(solid.shape[1]) if solid[:, x].any()], float)

	# Two lines meeting at the front corner, chosen by the smallest total error
	best = None
	for k in range(5, len(env) - 5):
		p0 = np.polyfit(env[:k + 1, 0], env[:k + 1, 1], 1)
		p1 = np.polyfit(env[k:, 0], env[k:, 1], 1)
		err = np.abs(np.polyval(p0, env[:k + 1, 0]) - env[:k + 1, 1]).sum() + np.abs(np.polyval(p1, env[k:, 0]) - env[k:, 1]).sum()
		if best is None or err < best[0]:
			best = (err, p0, p1)

	_, p0, p1 = best
	cx = (p1[1] - p0[1]) / (p0[0] - p1[0])
	left = np.array([env[0, 0], np.polyval(p0, env[0, 0])])
	corner = np.array([cx, np.polyval(p0, cx)])
	return left, corner


def base_quad(bid, img):
	"""Returns the base's left corner, front corner and unit direction of its right edge."""
	left, corner = fit_base(img)
	o = OVERRIDES.get(bid, {})
	left = np.array(o.get("L", left), float)
	corner = np.array(o.get("C", corner), float)
	t = math.radians(RIGHT_EDGE_DEG)
	return left, corner, np.array([math.cos(t), -math.sin(t)])


def warp(pad, quad, size):
	"""Perspective-maps pad's corners (TL, TR, BR, BL) onto quad in a canvas of size."""
	pw, ph = pad.size
	src = [(0, 0), (pw, 0), (pw, ph), (0, ph)]
	s = SUPERSAMPLE
	rows, rhs = [], []
	for (x, y), (u, v) in zip([(px * s, py * s) for px, py in quad], src):
		rows += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
		rhs += [u, v]
	coeffs = np.linalg.solve(np.array(rows, float), np.array(rhs, float))
	big = pad.convert("RGBa").transform((size[0] * s, size[1] * s), Image.PERSPECTIVE, coeffs, Image.BICUBIC)
	return big.resize(size, Image.LANCZOS).convert("RGBA")


def load_pad(name):
	img = Image.open(os.path.join(SRC, name)).convert("RGBA")
	a = np.asarray(img).copy()
	alpha = a[..., 3]
	alpha[alpha >= 240] = 255    # generated art has the pad body at alpha ~252
	alpha[alpha < 8] = 0
	img = Image.fromarray(a)
	return img.crop(img.getchannel("A").getbbox())


def build(bid, debug):
	img = Image.open(os.path.join(HD, f"{bid}.png")).convert("RGBA")
	left, corner, right_dir = base_quad(bid, img)
	w, h = img.size
	front = corner - left
	depth = DEPTH * np.linalg.norm(front)

	def at(u, v):
		"""u along the front edge (0 = left corner, 1 = front corner), v back along the right edge in pixels."""
		return left + u * front + v * right_dir

	# Pad corners TL, TR, BR, BL: its bottom edge is the front edge, pushed forward by the apron
	apron = APRON * w
	quad = [at(-SIDE, depth), at(1 + SIDE, depth), at(1 + SIDE, -apron), at(-SIDE, -apron)]

	# Grow the canvas evenly so the pad's centre stays the building's centre
	xs, ys = [p[0] for p in quad], [p[1] for p in quad]
	mx = int(math.ceil(max(0, -min(xs), max(xs) - w))) + 2
	my = int(math.ceil(max(0, -min(ys), max(ys) - h))) + 2
	size = (w + 2 * mx, h + 2 * my)
	quad = [(x + mx, y + my) for x, y in quad]

	cells = BUILDINGS[bid][1]
	for terrain in sorted(set(TERRAIN.values())):
		pad = load_pad(f"{'bib2' if cells >= 3 else 'bib3'}-{terrain}.png")
		out = warp(pad, quad, size)
		out.save(os.path.join(OUT, f"{bid}-{terrain}.png"), optimize=True)

		if debug:
			preview = Image.new("RGBA", size, (226, 222, 230, 255) if terrain == "snow" else (110, 118, 72, 255))
			preview.alpha_composite(out)
			preview.alpha_composite(img, (mx, my))
			os.makedirs(os.path.join(HERE, "preview"), exist_ok=True)
			preview.save(os.path.join(HERE, "preview", f"{bid}-{terrain}.png"))


def main():
	debug = "--debug" in sys.argv
	os.makedirs(OUT, exist_ok=True)

	lines = [
		"# High resolution foundation pads under the HD buildings (RedAlert Project X), drawn by WithPxBuildingPad.",
		"# GENERATED by artsrc/bibs/make_bibs.py - edit that script, not this file.",
		"",
	]
	for bid in PADDED:
		build(bid, debug)
		ox, oy = building_offset(bid)
		lines += [f"{bid}:", "\tpad:", f"\t\tFilename: ra|bits/hd/pads/{bid}-temperate.png", "\t\tTilesetFilenames:"]
		lines += [f"\t\t\t{ts}: ra|bits/hd/pads/{bid}-{TERRAIN[ts]}.png" for ts in TILESETS]
		lines += [f"\t\tScale: {1 / DENSITY:.4f}", f"\t\tOffset: {ox},{oy}", ""]

	with open(YAML, "w") as f:
		f.write("\n".join(lines))


if __name__ == "__main__":
	main()
