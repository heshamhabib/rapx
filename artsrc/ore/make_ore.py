#!/usr/bin/env python3
"""
Builds the HD gold ore and ore mine from the high resolution source art in src/.

Ore: src/ore-clumps.png holds 24 loose clumps in a 6x4 grid (rows: tiny, small, medium, large).
Each of the VARIANTS ore sequences gets DENSITIES frames; every frame adds clumps to the previous
one (bigger ones as the cell fills up), so a cell visibly grows as it regenerates. Frames are a bit
larger than a cell so neighbouring cells blend instead of showing the grid.

Gems: src/gem-clumps.png (same 6x4 layout as the gold, on magenta; prompt in gem-clumps-prompt.txt) is built
exactly like the gold, over GEM_DENSITIES frames (GEM_GROWTH). Without it, assets/environment/gems.png is used:
a cell shows one whole cluster that grows with density (GEM_CLUSTERS).

Mine: src/ore-mine.png (transparent, with a magenta-tinted shadow that is turned dark) is scaled
to MINE_CELLS cells wide.

Writes mods/rapx/bits/hd/ore/*.png and mods/rapx/sequences/hd-resources.yaml.

  python3 artsrc/ore/make_ore.py [--debug]    (--debug writes previews to artsrc/ore/preview/)
"""
import os
import random
import sys

import numpy as np
from PIL import Image, ImageFilter
from PIL.PngImagePlugin import PngInfo
from scipy.ndimage import label

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(HERE, "src")
OUT = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "ore")
YAML = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-resources.yaml")

DENSITY = 3.0
CELL = 72                 # 24px cells at 3x density
FRAME = 96                # frames spill a little into the neighbouring cells
TILESETS = ["TEMPERAT", "SNOW", "DESERT", "INTERIOR"]

VARIANTS = 4
DENSITIES = 12            # frames per variant, as in the classic gold01-04
CLUMP_SCALE = 0.16        # source pixels -> sprite pixels; a large clump becomes ~40px (13 world px)
SHADOW_OPACITY = 0.45

# Clump sizes (sheet rows 0-3) added at each density step, in order. The first frame is a
# few specks, the last a cell covered edge to edge so dense fields read as one carpet.
GROWTH = [[0], [0, 0], [1], [0, 1], [1, 0], [2], [1, 0], [2, 1], [2, 0], [3, 1], [2, 0], [3, 1]]

# Clumps go to the slots of a jittered SLOTS x SLOTS grid that covers the cell, in random order
SLOTS = 5

MINE_CELLS = 2.0

GEM_CLUMPS = os.path.join(SRC, "gem-clumps.png")
GEM_DENSITIES = 3         # MaxDensity of Gems in rules/world.yaml
# Clump sizes added at each density step; ends as full as the densest gold frame
GEM_GROWTH = [[0, 1, 0, 1, 2, 0, 1], [2, 1, 0, 2, 1, 0, 1], [3, 2, 1, 3, 2, 0, 1]]

GEMS = os.path.join(ROOT, "assets", "environment", "gems.png")
GEM_FRAME = 108           # clusters are a bit larger than a cell and their crystals reach up into the cell above
GEM_WIDTH = 84            # sprite px across the largest cluster's rocks and crystals (28 world px)
# Cluster (sheet order, smallest first) shown at each density step, per variant; variants 2-3 are mirrored
GEM_CLUSTERS = [[0, 1, 2], [0, 1, 3], [0, 1, 2], [0, 1, 3]]


def load_clumps(path):
	"""Returns clumps[row] = list of RGBA images, cut out of the 6x4 sheet (transparent, or on magenta)."""
	img = Image.open(path).convert("RGBA")
	a = np.asarray(img)
	if a[..., 3].min() == 255:
		sys.path.insert(0, os.path.join(ROOT, "artsrc", "buildings"))
		from process_building import key
		rgba, _ = key(a[..., :3].astype(np.float32) / 255, 0)
		a = (np.clip(rgba, 0, 1) * 255).astype(np.uint8)
	labels, n = label(a[..., 3] > 24)
	h, w = labels.shape
	cols, rows = 6, 4
	groups = {}
	for i in range(1, n + 1):
		ys, xs = np.nonzero(labels == i)
		if len(xs) < 20:
			continue

		# Assign each piece to the grid slot its centre falls in, so touching clumps stay apart
		slot = (min(int(ys.mean() * rows / h), rows - 1), min(int(xs.mean() * cols / w), cols - 1))
		groups.setdefault(slot, []).append(i)

	clumps = [[] for _ in range(rows)]
	for (row, col), ids in sorted(groups.items()):
		mask = np.isin(labels, ids)
		ys, xs = np.nonzero(mask)
		box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
		piece = a.copy()
		piece[..., 3] = np.where(mask, piece[..., 3], 0)
		piece = Image.fromarray(piece).crop(box)
		size = (max(1, round(piece.width * CLUMP_SCALE)), max(1, round(piece.height * CLUMP_SCALE)))
		clumps[row].append(piece.convert("RGBa").resize(size, Image.LANCZOS).convert("RGBA"))

	return clumps


def with_shadow(clump):
	"""Adds a soft contact shadow under a clump."""
	pad = 6
	out = Image.new("RGBA", (clump.width + 2 * pad, clump.height + 2 * pad))
	shadow = Image.new("RGBA", out.size)
	alpha = Image.new("L", out.size)
	alpha.paste(clump.getchannel("A"), (pad + 2, pad + 3))
	alpha = alpha.filter(ImageFilter.GaussianBlur(2.5)).point(lambda v: int(v * SHADOW_OPACITY))
	shadow.putalpha(alpha)
	out.alpha_composite(shadow)
	out.alpha_composite(clump, (pad, pad))
	return out


def slots(rng):
	"""Clump centres: a jittered grid over the cell, shuffled so early clumps are spread out."""
	step = CELL / SLOTS
	result = [(-CELL / 2 + (i + 0.5) * step + rng.uniform(-0.35, 0.35) * step,
		-CELL / 2 + (j + 0.5) * step + rng.uniform(-0.35, 0.35) * step)
		for i in range(SLOTS) for j in range(SLOTS)]
	rng.shuffle(result)
	return result


def build_variant(clumps, seed, growth=GROWTH):
	rng = random.Random(seed)
	bags = [rng.sample(row, len(row)) for row in clumps]
	centres = slots(rng)
	placed = []     # (centre, clump image)
	frames = []
	for step in growth:
		for row in step:
			clump = with_shadow(bags[row].pop() if bags[row] else rng.choice(clumps[row]))
			placed.append((centres.pop(), clump))

		frame = Image.new("RGBA", (FRAME, FRAME))
		for (cx, cy), clump in sorted(placed, key=lambda pc: pc[0][1] + pc[1].height / 2):
			frame.alpha_composite(clump, (round(FRAME / 2 + cx - clump.width / 2), round(FRAME / 2 + cy - clump.height / 2)))
		frames.append(frame)

	return frames


def build_mine():
	img = Image.open(os.path.join(SRC, "ore-mine.png")).convert("RGBA")
	a = np.asarray(img).astype(np.float32)
	rgb, alpha = a[..., :3], a[..., 3]

	# The shadow is magenta-tinted: make it a plain dark shadow
	magenta = (np.minimum(rgb[..., 0], rgb[..., 2]) - rgb[..., 1]) > 25
	rgb[magenta] = 0
	alpha[magenta] *= 0.6
	alpha[alpha < 6] = 0
	img = Image.fromarray(np.dstack([rgb, alpha]).astype(np.uint8))

	# The rock without its shadow sets the scale and the centre
	solid = Image.fromarray(((alpha > 200) & ~magenta).astype(np.uint8) * 255)
	x0, y0, x1, y1 = solid.getbbox()
	full = img.getchannel("A").getbbox()

	scale = MINE_CELLS * CELL / (x1 - x0)
	cropped = img.crop(full)
	size = (round(cropped.width * scale), round(cropped.height * scale))
	out = cropped.convert("RGBa").resize(size, Image.LANCZOS).convert("RGBA")
	out.save(os.path.join(OUT, "mine.png"), optimize=True)

	# Offset (sprite pixels) that puts the rock's centre, not the shadow's, on the cell centre
	cx = ((x0 + x1) / 2 - full[0]) * scale
	cy = ((y0 + y1) / 2 - full[1]) * scale
	return round(size[0] / 2 - cx), round(size[1] / 2 - cy)


def load_gem_clusters():
	"""The 4 whole clusters of the gem sheet (with their shadows), smallest first, and the bounding box of each
	cluster's solid part. Pieces go to the quadrant their centre is in, as crystal tips poke into the next one."""
	sys.path.insert(0, os.path.join(ROOT, "artsrc", "buildings"))
	from process_building import key
	from scipy.ndimage import binary_dilation
	img = np.asarray(Image.open(GEMS).convert("RGB"), np.float32) / 255
	rgba, solid = key(img, SHADOW_OPACITY)

	# key() judges by "how magenta", so the purple crystals come out translucent and grey. The backdrop and its
	# shadow have no green at all, so anything with some green is solid and keeps its source colour.
	green = np.clip((img[..., 1] / np.maximum(img.max(2), 1e-3) - 0.04) / 0.12, 0, 1)
	solid = np.maximum(solid, green)
	rgba[..., 3] = np.maximum(rgba[..., 3], green)
	rgba[..., :3] = np.where((solid > 0.9)[..., None], img, rgba[..., :3])

	h, w = solid.shape
	labels, n = label(binary_dilation(rgba[..., 3] > 0.02, iterations=3))
	owner = np.zeros(n + 1, int)
	for i in range(1, n + 1):
		ys, xs = np.nonzero(labels == i)
		owner[i] = int(ys.mean() >= h / 2) * 2 + int(xs.mean() >= w / 2) + 1
	clusters = []
	for q in range(1, 5):
		mask = (owner[labels] == q) & (labels > 0)
		piece = rgba.copy()
		piece[..., 3] *= mask
		ys, xs = np.nonzero(mask & (solid > 0.5))
		im = Image.fromarray((np.clip(piece, 0, 1) * 255).astype(np.uint8))
		full = im.getchannel("A").point(lambda v: 255 if v > 4 else 0).getbbox()
		box = (xs.min() - full[0], ys.min() - full[1], xs.max() + 1 - full[0], ys.max() + 1 - full[1])
		clusters.append((len(xs), im.crop(full), box))
	clusters.sort(key=lambda c: c[0])
	return [c[1:] for c in clusters]


def save_sheet(frames, name):
	sheet = Image.new("RGBA", (FRAME * len(frames), FRAME))
	for i, f in enumerate(frames):
		sheet.paste(f, (i * FRAME, 0))
	meta = PngInfo()
	meta.add_text("FrameSize", f"{FRAME},{FRAME}")
	meta.add_text("FrameAmount", str(len(frames)))
	sheet.save(os.path.join(OUT, name), pnginfo=meta, optimize=True)
	return sheet


def build_gem_clusters():
	"""Fallback without src/gem-clumps.png: one whole cluster per cell, bigger at each density step (GEM_CLUSTERS)."""
	clusters = load_gem_clusters()
	scale = GEM_WIDTH / (clusters[-1][1][2] - clusters[-1][1][0])
	names = []
	for v, order in enumerate(GEM_CLUSTERS):
		rng = random.Random(100 + v)
		sheet = Image.new("RGBA", (GEM_FRAME * GEM_DENSITIES, GEM_FRAME))
		for d, c in enumerate(order):
			src, (x0, y0, x1, y1) = clusters[c]
			s = scale * rng.uniform(0.94, 1.04)
			im = src.convert("RGBa").resize((round(src.width * s), round(src.height * s)), Image.LANCZOS).convert("RGBA")
			im = im.filter(ImageFilter.UnsharpMask(radius=1, percent=60, threshold=2))
			cx, cy = (x0 + x1) / 2 * s, (y0 + y1) / 2 * s
			if v >= 2:
				im = im.transpose(Image.FLIP_LEFT_RIGHT)
				cx = im.width - cx

			# Centre the solid part on the cell, nudged up a little so the rubble base sits on the cell
			ox, oy = rng.uniform(-3, 3), rng.uniform(-3, 1) - 4
			frame = Image.new("RGBA", (GEM_FRAME, GEM_FRAME))
			frame.paste(im, (round(GEM_FRAME / 2 + ox - cx), round(GEM_FRAME / 2 + oy - cy)))
			sheet.paste(frame, (d * GEM_FRAME, 0))
		meta = PngInfo()
		meta.add_text("FrameSize", f"{GEM_FRAME},{GEM_FRAME}")
		meta.add_text("FrameAmount", str(GEM_DENSITIES))
		name = f"gem{v + 1:02}.png"
		sheet.save(os.path.join(OUT, name), pnginfo=meta, optimize=True)
		names.append(name)
	return names


def seq(name, filename, extra):
	lines = [f"\t{name}:", f"\t\tFilename: ra|bits/hd/ore/{filename}", "\t\tTilesetFilenames:"]
	lines += [f"\t\t\t{ts}: ra|bits/hd/ore/{filename}" for ts in TILESETS]
	return lines + [f"\t\tScale: {1 / DENSITY:.4f}"] + extra


def main():
	debug = "--debug" in sys.argv
	os.makedirs(OUT, exist_ok=True)
	clumps = load_clumps(os.path.join(SRC, "ore-clumps.png"))
	print("clumps per size:", [len(r) for r in clumps])

	yaml = [
		"# High resolution gold ore and ore mine (RedAlert Project X).",
		"# GENERATED by artsrc/ore/make_ore.py - edit that script, not this file.",
		"",
		"resources:",
	]
	sheets = []
	for v in range(VARIANTS):
		name = f"gold{v + 1:02}.png"
		sheets.append(save_sheet(build_variant(clumps, seed=v + 1), name))
		yaml += seq(f"gold{v + 1:02}", name, ["\t\tStart: 0", f"\t\tLength: {DENSITIES}"])

	gem_names = []
	if os.path.exists(GEM_CLUMPS):
		gem_clumps = load_clumps(GEM_CLUMPS)
		print("gem clumps per size:", [len(r) for r in gem_clumps])
		for v in range(VARIANTS):
			gem_names.append(f"gem{v + 1:02}.png")
			save_sheet(build_variant(gem_clumps, seed=100 + v, growth=GEM_GROWTH), gem_names[-1])
	elif os.path.exists(GEMS):
		gem_names = build_gem_clusters()
	for v, name in enumerate(gem_names):
		yaml += seq(f"gem{v + 1:02}", name, ["\t\tStart: 0", f"\t\tLength: {GEM_DENSITIES}"])

	ox, oy = build_mine()
	yaml += ["", "mine:"] + seq("idle", "mine.png", [f"\t\tOffset: {ox},{oy}", "\t\tZOffset: -2c512"]) + [""]
	with open(YAML, "w") as f:
		f.write("\n".join(yaml))

	if debug:
		os.makedirs(os.path.join(HERE, "preview"), exist_ok=True)
		for bg_name, bg in [("snow", (226, 222, 230, 255)), ("temperate", (110, 118, 72, 255))]:
			preview = Image.new("RGBA", (FRAME * DENSITIES, FRAME * VARIANTS), bg)
			for v, sheet in enumerate(sheets):
				preview.alpha_composite(sheet, (0, v * FRAME))
			preview.save(os.path.join(HERE, "preview", f"ore-{bg_name}.png"))


if __name__ == "__main__":
	main()
