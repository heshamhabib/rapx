#!/usr/bin/env python3
"""
HD remaster of the classic terrain edge tiles (cliffs, water cliffs, rivers, beaches), without AI renders.

The HD terrain shader (shaders/terrain_detail.frag) re-textures the classic tiles one screen pixel at a time, so the
boundaries between rock, ground and water keep the blocky shape of the classic 24 px cells. This script rebuilds
each of those templates offline, where it can look at the whole template:

  1. classic template -> per-pixel material weights (ground / dirt / rock / water) from the same reference colours
     the shader uses (rules/palettes.yaml), with water only allowed in water / river / beach cells;
  2. weights upscaled to 3x, blurred and broken up with soft noise, then sharpened: smooth, organic boundaries;
  3. each material filled with the shader's own photo textures (bits/terrain/<tileset>-*.png), lit by the
     classic art's light and dark (upscaled smoothly), so cliffs keep their faces and shadows;
  4. ambient occlusion at the foot of rock, a soft wet edge along water;
  5. water is left transparent, so the shader's animated HD water shows through.

Output: mods/rapx/bits/hd/tiles/<tileset dir>/<template image>.png at 72 px per cell, drawn by the PxHDTiles world
trait over every map cell that uses the template. Templates with an AI render in assets/env/tiles (fords, debris;
make_tiles.py) are not touched, except bridges: their banks are remastered like a river, and only the bridge itself
(deck, railings, arches, cut along the classic outline) is taken from the AI render, aligned to the classic art first,
so the HD river runs under it and the pieces join. Classic templates are cached in artsrc/env-inventory/classic-terrain/.

  python3 artsrc/env/make_terrain_tiles.py [--tileset snow] [--only s01,rv01] [--force] [--preview out.png]
"""
import argparse
import glob
import os
import re
import sys
import zlib

import numpy as np
from PIL import Image
from scipy.ndimage import affine_transform, distance_transform_edt, gaussian_filter, label, median_filter, zoom

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MOD = os.path.join(ROOT, "mods", "rapx")
OUT = os.path.join(MOD, "bits", "hd", "tiles")
AI_TILES = os.path.join(ROOT, "assets", "env", "tiles")
CACHE = os.path.join(ROOT, "artsrc", "env-inventory", "classic-terrain")
sys.path.insert(0, os.path.join(ROOT, "artsrc", "env-inventory"))
import export_classic  # noqa: E402  (utility / frames / assemble helpers)

CATEGORIES = {"Cliffs", "Water Cliffs", "River", "Beach", "Road", "Bridge"}
SCALE = 3            # HD pixels per classic pixel (72 px per 24 px cell)
FEATHER = 4          # HD pixels over which a template's missing cells fade out
ROAD_FADE = (2, 26)
BRIDGE_STONE = {"snow": (0.50, 0.51, 0.55), "temperat": (0.52, 0.49, 0.44), "desert": (0.66, 0.56, 0.44)}
BRIDGE_SCALES = (0.9, 0.95, 1.0, 1.05, 1.1)   # AI bridge render alignment search
BRIDGE_SHIFTS = range(-36, 37, 6)            # HD pixels
BRIDGE_REACH = 10    # classic pixels beyond the Bridge cells that are still painted as bridge (railing ends)  # HD pixels from the outer border over which faded road templates go from clear to opaque

# Per tileset: tileset file, classic palette, texture prefix, reference colours (as in rules/palettes.yaml) and the
# world pixels per texture repeat (TerrainDetailTexturesInfo defaults)
TILESETS = {
    "snow": dict(yaml="snow.yaml", pal="snow.pal", tex="snow", ground=["E1DDE1", "C1BBBB"], dirt=["9D9286"],
                 rock=["5E5E5C", "433D37", "151518"], water=["747E87", "688397"],
                 # Snow maps also run their tracks out into plain snow (see desert)
                 fade_roads=True,
                 # The AI ford renders are opaque photo squares that don't match the remastered river around
                 # them: remaster fords like the bridge ends instead (bank + Road cells as road)
                 remaster_fords=True),
    "desert": dict(yaml="desert.yaml", pal="desert.pal", tex="desert", ground=["8A5F46", "785741"], dirt=["A27A4E"],
                   rock=["C6996A", "523E2E", "36291F"], water=["70868C"],
                   # Desert maps lay whole road templates next to plain sand; a hard template border reads as a
                   # square patch, so roads fade out (noisily) towards their outer border and the shader's own
                   # organic sand / dirt boundary (EdgeWarp in rules/palettes.yaml) shows through
                   fade_roads=True),
    # Temperate has no reference colours in palettes.yaml (the shader uses hue rules); these are measured from
    # the classic temperate palette: grass greens, path browns, cliff greys, sea blue
    "temperat": dict(yaml="temperat.yaml", pal="temperat.pal", tex="temperate", ground=["4C6C30", "5C7C38", "3C5428"],
                     dirt=["8C7050", "6C5438"], rock=["A0A0A0", "707070", "484848", "282828"], water=["384C70", "2C3C5C"]),
}
REPEAT = {"ground": 96, "dirt": 120, "rock": 96}       # world pixels per repeat
WATER_TYPES = {"Water", "River", "Beach", "Bridge"}
CLASSES = ("ground", "dirt", "rock", "water")


def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255


def parse_templates(path, ts=None):
    """[{img, size, cat, tiles: {cell index: terrain type}, bridge_cells}] for the templates we remaster."""
    out, cur = [], None
    for line in open(path):
        line = line.rstrip("\n")
        if re.match(r"^\tTemplate@", line):
            if cur and cur.get("cat") in CATEGORIES and cur.get("img"):
                out.append(cur)
            cur = {"tiles": {}}
        elif cur is None:
            continue
        elif m := re.match(r"^\t\tImages: (.+)$", line):
            cur["img"] = m.group(1).split(",")[0].strip()
        elif m := re.match(r"^\t\tSize: (\d+),(\d+)$", line):
            cur["size"] = (int(m.group(1)), int(m.group(2)))
        elif m := re.match(r"^\t\tCategories: (.+)$", line):
            cur["cat"] = m.group(1).strip()
        elif m := re.match(r"^\t\t\t(\d+): (\w+)$", line):
            cur["tiles"][int(m.group(1))] = m.group(2)
    if cur and cur.get("cat") in CATEGORIES and cur.get("img"):
        out.append(cur)

    # Bridge templates: the cells of the bridge itself (deck, railings, arches). Damaged / destroyed templates mark
    # none, so they use the intact template's (same family and size); fords and odd pieces get none
    def family(t):
        m = re.match(r"(br\d|s?bridge\d)", stem(t))
        return (m.group(0) if m else None, t["size"])
    intact = {family(t): [i for i, ty in t["tiles"].items() if ty == "Bridge"]
              for t in out if t["cat"] == "Bridge" and "Bridge" in t["tiles"].values()}
    for t in out:
        if t["cat"] == "Bridge":
            own = [i for i, ty in t["tiles"].items() if ty == "Bridge"]
            t["bridge_cells"] = own or (intact.get(family(t), []) if family(t)[0] else [])
            # bridge ends (br1x, bridge1x, ...): bank and the road ramp onto the bridge, remastered like a river with
            # the Road cells as road; fords (f01, ford1, fjord1) keep their AI render unless remaster_fords
            t["ramp"] = not t["bridge_cells"] and family(t)[0] is not None
            if TILESETS.get(ts, {}).get("remaster_fords") and re.match(r"(f\d\d|ford\d|fjord\d)$", stem(t)):
                t["ramp"] = True
    return out


def export_templates(ts, templates, force):
    """Classic templates at 1x (RGBA, missing cells transparent), cached as PNG."""
    cache = os.path.join(CACHE, ts)
    os.makedirs(cache, exist_ok=True)
    todo = [t for t in templates if force or not os.path.exists(os.path.join(cache, stem(t) + ".png"))]
    if todo:
        pal = TILESETS[ts]["pal"]
        files = sorted({t["img"] for t in todo})
        export_classic.utility("--extract", *files, pal)
        try:
            for t in todo:
                fr = export_classic.frames(t["img"], pal)
                if not fr:
                    print("  could not export", t["img"])
                    continue
                w, h = t["size"]
                export_classic.assemble(fr, w, h).save(os.path.join(cache, stem(t) + ".png"))
        finally:
            for f in files + [pal]:
                p = os.path.join(export_classic.ENGINE, f)
                if os.path.exists(p):
                    os.remove(p)
    return {stem(t): np.asarray(Image.open(os.path.join(cache, stem(t) + ".png")).convert("RGBA")).astype(np.float32) / 255
            for t in templates if os.path.exists(os.path.join(cache, stem(t) + ".png"))}


def stem(t):
    return os.path.splitext(t["img"])[0]


def load_texture(ts, kind, size_px):
    """The shader's texture, scaled so one repeat covers `size_px` HD pixels, as float RGB."""
    name = {"ground": "clear", "dirt": "road", "rock": "cliff"}[kind]
    im = Image.open(os.path.join(MOD, "bits", "terrain", f"{TILESETS[ts]['tex']}-{name}.png")).convert("RGB")
    im = im.resize((size_px, size_px), Image.LANCZOS)
    return np.asarray(im).astype(np.float32) / 255


def tile_texture(tex, h, w, ox, oy):
    th, tw = tex.shape[:2]
    ys = (np.arange(h) + oy) % th
    xs = (np.arange(w) + ox) % tw
    return tex[ys][:, xs]


def lum(rgb):
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def smooth(x, lo, hi):
    t = np.clip((x - lo) / (hi - lo), 0, 1)
    return t * t * (3 - 2 * t)


def band(x, lo, hi, soft):
    return smooth(x, lo - soft, lo + soft) * (1 - smooth(x, hi - soft, hi + soft))


def hls(rgb):
    mx, mn = rgb.max(-1), rgb.min(-1)
    l = (mx + mn) / 2
    d = mx - mn
    s = np.where(d < 1e-6, 0, d / np.maximum(1e-6, 1 - np.abs(2 * l - 1)))
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.where(mx == r, ((g - b) / np.maximum(d, 1e-6)) % 6, np.where(mx == g, (b - r) / np.maximum(d, 1e-6) + 2,
                                                                      (r - g) / np.maximum(d, 1e-6) + 4)) / 6
    return np.where(d < 1e-6, 0, h), l, s


def class_weights(ts, rgb):
    """Soft (ground, dirt, rock, water) weights from the classic palette colours, measured per tileset."""
    blurred = np.stack([gaussian_filter(rgb[..., c], 0.6) for c in range(3)], -1)
    h, l, s = hls(blurred)
    # Water: blue / teal, a little saturated, mid lightness (gated to water cells by the caller)
    sat_lo, sat_hi = (0.05, 0.11) if ts == "desert" else (0.10, 0.20)
    water = band(h, 0.48, 0.66, 0.03) * smooth(s, sat_lo, sat_hi) * band(l, 0.36, 0.78, 0.05)
    if ts == "snow":
        ground = smooth(l, 0.66, 0.78)                                  # snow
        dirt = np.zeros_like(l)
    elif ts == "temperat":
        # Classic temperate grass is dark and only slightly green (e.g. 28302C, 344128, 284528)
        ground = band(h, 0.16, 0.47, 0.03) * smooth(s, 0.04, 0.10) * smooth(l, 0.08, 0.13)   # grass
        dirt = band(h, 0.03, 0.13, 0.02) * smooth(s, 0.12, 0.2) * band(l, 0.30, 0.55, 0.04)  # earth banks
    else:  # desert: nearest reference colour, as the shader does (classic sand and cliff share hue and lightness)
        return reference_weights(ts, rgb)
    water = water * (1 - ground)
    ground = ground * (1 - water)
    dirt = dirt * (1 - ground) * (1 - water)
    rock = np.clip(1 - ground - dirt - water, 0, 1)
    w = np.stack([ground, dirt, rock, water], -1) + 1e-4
    return w / w.sum(-1, keepdims=True)


def reference_weights(ts, rgb, softness=0.05):
    """Soft (ground, dirt, rock, water) weights: soft-min over the tileset's reference colours, like
    ClassifyByReference in shaders/terrain_detail.frag, on a slightly wider blur (dithered sand)."""
    blurred = np.stack([gaussian_filter(rgb[..., c], 1.2) for c in range(3)], -1)
    refs = [(hexrgb(c), k) for k, name in enumerate(CLASSES) for c in TILESETS[ts][name]]
    d = np.stack([((blurred - c) ** 2).sum(-1) for c, _ in refs], -1)
    e = np.exp(-(d - d.min(-1, keepdims=True)) / (2 * softness * softness))
    w = np.stack([e[..., [i for i, (_, k) in enumerate(refs) if k == cls]].sum(-1) for cls in range(4)], -1) + 1e-4
    return w / w.sum(-1, keepdims=True)


def bridge_colour(ts, rgb1, tex, H, W, rng):
    """Deck, railings and arches: the classic art's light and dark (median-filtered to drop the dithering, upscaled,
    re-sharpened) over a clean stone colour with a little HD grain, plus drifted snow on the snow tileset."""
    L1 = median_filter(lum(rgb1), size=3)
    L = np.clip(zoom(gaussian_filter(L1, 0.5), SCALE, order=3)[:H, :W], 0, 1)
    L = L + (L - gaussian_filter(L, 2.5)) * 1.0             # crisp railing and arch edges
    shade = np.clip(L / max(float(np.median(L)), 1e-3), 0.2, 1.7)
    grain = lum(tex["rock"]) / max(1e-3, float(lum(tex["rock"].reshape(-1, 3).mean(0)[None, None])[0, 0]))
    stone = np.array(BRIDGE_STONE.get(ts, (0.55, 0.52, 0.48)), np.float32)
    col = stone * (shade * (1 + (grain - 1) * 0.25))[..., None]
    if ts == "snow":
        snow_col = tex["ground"].reshape(-1, 3).mean(0)
        drift = smooth(gaussian_filter(rng.standard_normal((H, W)), 7) * 14, 0.1, 0.9) * 0.8
        drift = np.maximum(drift, smooth(shade, 1.15, 1.45) * 0.75)      # snow on the railing tops
        drift *= smooth(shade, 0.6, 0.9)                                 # not in the shadows / arches
        drift = gaussian_filter(drift, 1.2)
        col = col * (1 - drift[..., None]) + snow_col * np.clip(0.8 + 0.2 * shade, 0, 1.1)[..., None] * drift[..., None]
    return np.clip(col, 0, 1)


def warp(img, scale, dx, dy):
    """Scale `img` (H x W [x C]) about its centre and shift it by (dx, dy) HD pixels."""
    H, W = img.shape[:2]
    m = np.diag([1 / scale, 1 / scale])
    off = [H / 2 - (H / 2 + dy) / scale, W / 2 - (W / 2 + dx) / scale]
    if img.ndim == 2:
        return affine_transform(img, m, offset=off, order=1, mode="mirror")
    return np.stack([affine_transform(img[..., k], m, offset=off, order=1, mode="mirror") for k in range(img.shape[2])], -1)


def ai_bridge_colour(path, rgb1, a1, H, W):
    """The AI render's bridge, lined up with the classic art: the scale / shift whose railing and arch edges best
    match the classic's (normalised correlation of band-passed luminance). Where the render still has water inside
    the classic bridge outline, the gap is filled from the surrounding bridge pixels. Also returns where the render
    is solid (not its water), so its side walls and arches stay even where the classic art has water."""
    ai = np.asarray(Image.open(path).convert("RGB").resize((W, H), Image.LANCZOS)).astype(np.float32) / 255
    band_pass = lambda L: gaussian_filter(L, 2) - gaussian_filter(L, 10)
    present = zoom((a1 > 0).astype(np.float32), SCALE, order=0)[:H, :W]
    A = band_pass(np.clip(zoom(lum(rgb1), SCALE, order=1)[:H, :W], 0, 1)) * present
    L = lum(ai)
    best = (-2.0, 1.0, 0, 0)
    for sc in BRIDGE_SCALES:
        for dx in BRIDGE_SHIFTS:
            for dy in BRIDGE_SHIFTS:
                B = band_pass(warp(L, sc, dx, dy)) * present
                r = (A * B).sum() / np.sqrt((A * A).sum() * (B * B).sum() + 1e-9)
                if r > best[0] + 0.01:      # prefer no change unless it clearly fits better
                    best = (r, sc, dx, dy)
    ai = np.clip(warp(ai, *best[1:]), 0, 1)

    # The render's own water (dark saturated blue-teal) has no place on the bridge: fill it from nearby bridge
    hh, ll, ss = hls(np.stack([gaussian_filter(ai[..., c], 2) for c in range(3)], -1))
    wet = band(hh, 0.45, 0.70, 0.02) * smooth(ss, 0.15, 0.25) * (1 - smooth(ll, 0.5, 0.6))
    ok = gaussian_filter(1 - wet, 1.0)
    fill = np.stack([gaussian_filter(ai[..., c] * ok, 8) for c in range(3)], -1) / np.maximum(gaussian_filter(ok, 8), 1e-3)[..., None]
    return ai * (1 - wet[..., None]) + fill * wet[..., None], gaussian_filter(1 - wet, 1.5)


def remaster(ts, t, classic, textures, rng):
    road = t["cat"] == "Road"
    w_cells, h_cells = t["size"]
    rgb1, a1 = classic[..., :3].copy(), classic[..., 3]
    H1, W1 = a1.shape
    # Cells the template doesn't have are transparent black: fill them with the nearest real pixels so they don't
    # read as dark rock and bleed a dark line into the visible cells when the masks are blurred
    empty = a1 == 0
    if empty.any() and not empty.all():
        _, (iy, ix) = distance_transform_edt(empty, return_indices=True)
        rgb1 = rgb1[iy, ix]

    # 1. Material weights at classic resolution; water only in water / river / beach cells (dilated one pixel)
    w1 = class_weights(ts, rgb1)
    w1[empty] = (1, 0, 0, 0)          # and they count as plain ground (transparent)
    if road:
        w1[..., 1] += w1[..., 2]
        w1[..., 2] = 0
    elif t.get("ramp"):
        ramp = np.zeros((h_cells, w_cells), np.float32)
        for i, ty in t["tiles"].items():
            if ty == "Road":
                ramp[i // w_cells, i % w_cells] = 1
        ramp = np.clip(gaussian_filter(np.kron(ramp, np.ones((24, 24), np.float32)), 4) * 1.5, 0, 1)
        w1[..., 1] += w1[..., 2] * ramp
        w1[..., 2] *= 1 - ramp
    # (plain land cliffs only: their dark blue-grey shadows must not turn into water; water cliffs, rivers and
    # beaches mark their water cells as Rock or Beach, so they keep all their water)
    if t["cat"] == "Cliffs":
        water_ok = np.zeros((h_cells, w_cells), np.float32)
        for i, ty in t["tiles"].items():
            if ty in WATER_TYPES:
                water_ok[i // w_cells, i % w_cells] = 1
    else:
        water_ok = np.ones((h_cells, w_cells), np.float32)
    water_ok = np.kron(water_ok, np.ones((24, 24), np.float32))
    water_ok = np.clip(gaussian_filter(water_ok, 2.0) * 2, 0, 1)
    moved = w1[..., 3] * (1 - water_ok)
    w1[..., 3] -= moved
    w1[..., 2] += moved

    # 2. Upscale smoothly, blur, break up with soft noise, sharpen
    H, W = H1 * SCALE, W1 * SCALE
    wh = np.stack([zoom(w1[..., k], SCALE, order=1)[:H, :W] for k in range(4)], -1)
    # Roads draw their diagonals as whole-cell steps in the classic art: they need a much wider blur
    blur = (14, 14, 14, 14) if road else (1.8, 1.8, 1.8, 2.4)
    wh = np.stack([gaussian_filter(wh[..., k], blur[k], mode="nearest") for k in range(4)], -1)
    noise = gaussian_filter(rng.standard_normal((H, W)), 6) * 6
    wh[..., 2] *= np.exp(noise * 0.25)            # rock edges wander a little
    wh = np.clip(wh, 1e-6, None) ** 4
    wh /= wh.sum(-1, keepdims=True)

    # Bridges: the deck, railings and arches are man-made, so inside the Bridge cells (and a little beyond, where
    # the railings reach into the bank cells) they are painted from the classic art instead of as rock, and nothing
    # there is left transparent as ground except the water under the arches
    struct = np.zeros((H, W), np.float32)
    if t.get("bridge_cells"):
        cells = np.zeros((h_cells, w_cells), bool)
        for i in t["bridge_cells"]:
            cells[i // w_cells, i % w_cells] = True
        near = distance_transform_edt(~np.kron(cells, np.ones((24, 24), bool))) <= BRIDGE_REACH
        struct1 = np.clip(gaussian_filter(near.astype(np.float32), 3.0) * 1.6 - 0.3, 0, 1) * (a1 > 0)
        struct = np.clip(zoom(struct1, SCALE, order=1)[:H, :W], 0, 1)
        moved = wh[..., 0] * struct
        wh[..., 0] -= moved
        wh[..., 2] += moved

    # 3. The classic art upscaled smoothly: its light and dark keep the cliff faces, boulders and shadows
    rgbh = np.stack([np.clip(zoom(rgb1[..., c], SCALE, order=3)[:H, :W], 0, 1) for c in range(3)], -1)
    rgbh = np.stack([gaussian_filter(rgbh[..., c], 0.9) for c in range(3)], -1)
    L = lum(rgbh)
    L1 = lum(rgb1)
    Lsoft = gaussian_filter(L, 9)
    ox, oy = rng.integers(0, 4096, 2)
    tex = {k: tile_texture(textures[k], H, W, ox, oy) for k in ("ground", "dirt", "rock")}

    def ref(k, default):
        m = w1[..., k] * (a1 > 0)
        return float((L1 * m).sum() / m.sum()) if m.sum() > 20 else default
    rock_ref, ground_ref, dirt_ref = ref(2, 0.35), ref(0, 0.8), ref(1, 0.45)

    def tone(t):
        """Mean colour of a texture and its normalised detail (1 = average)."""
        m = t.reshape(-1, 3).mean(0)
        return m, lum(t) / max(1e-3, lum(m[None, None])[0, 0])

    # Rock: HD photo texture for the detail; the shape comes from a height field built from the smooth rock
    # outline (distance from the edge), lit from the top-left like the rest of the art. Only the broad light and
    # dark of the classic art is kept (its fine pixels are too coarse to scale up).
    rock_mask = wh[..., 2]
    dist = distance_transform_edt(rock_mask > 0.5) - distance_transform_edt(rock_mask <= 0.5)
    hgt = np.clip(dist, -4, 16) / 16
    rock_col, rock_detail = tone(tex["rock"])
    hgt = gaussian_filter(hgt, 2.5) + (rock_detail - 1) * 0.12 + gaussian_filter(L - Lsoft, 1.5) * 0.6
    gy, gx = np.gradient(hgt * 9)
    nrm = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    light = np.array([-0.55, -0.6, 0.58])
    light /= np.linalg.norm(light)
    diffuse = np.clip((nrm * light).sum(-1), 0, 1)
    broad = np.clip(gaussian_filter(L, 3) / rock_ref, 0.35, 1.7) ** 0.95
    rock = tex["rock"] * ((0.32 + 0.95 * diffuse) * broad)[..., None]
    if ts == "snow":
        # Snow settles on the tops and the sun-facing, upward faces of the rock
        snow_col = tex["ground"].reshape(-1, 3).mean(0)
        cap = smooth(nrm[..., 2], 0.88, 0.97) * smooth(hgt, 0.45, 0.85) * 0.5
        cap = np.maximum(cap, smooth(L, rock_ref * 1.7, rock_ref * 2.3) * 0.5)
        rock = rock * (1 - cap[..., None]) + (snow_col * (0.75 + 0.3 * diffuse[..., None])) * cap[..., None]

    # Ground and dirt: their texture with the classic's broad shading (shadows next to cliffs)
    ground = tex["ground"] * np.clip(Lsoft / ground_ref, 0.62, 1.04)[..., None]
    dirt_col, dirt_detail = tone(tex["dirt"])
    dirt = tex["dirt"] * np.clip(Lsoft / dirt_ref, 0.55, 1.15)[..., None]

    # 4. Only rock and dirt/road are painted; the snow/grass/sand ground stays transparent so the HD terrain
    #    shader's ground (world-aligned, seamless) shows through. Rock and dirt are widened by one classic pixel so
    #    the shader's blocky version of them never peeks out at the edges. Ground near rock and water gets a
    #    soft dark overlay: ambient occlusion at the foot of the cliffs, damp ground along the shore.
    paint = wh[..., 1] + wh[..., 2]
    paint_d = np.clip(gaussian_filter(np.clip((paint - 0.5) * 3 + 0.5, 0, 1), 1.2) * 1.0, 0, 1)
    grown = np.clip(gaussian_filter((distance_transform_edt(paint < 0.5) <= SCALE).astype(np.float32), 1.0), 0, 1)
    paint_a = np.maximum(paint_d, grown * 0.97)
    land = 1 - wh[..., 3]
    painted = (wh[..., 1:2] * dirt + wh[..., 2:3] * rock) / np.maximum(paint, 1e-3)[..., None]
    # where the widened edge reaches beyond the material, keep the nearest material colour (blurred)
    fill = np.stack([gaussian_filter(painted[..., c] * paint, 3) / np.maximum(gaussian_filter(paint, 3), 1e-3)
                     for c in range(3)], -1)
    painted = np.where((paint > 0.3)[..., None], painted, fill)
    if struct.any():
        if t.get("ai") and t.get("bridge_cells"):
            bridge, solid_ai = ai_bridge_colour(t["ai"], rgb1, a1, H, W)
            land = np.maximum(land, solid_ai * struct)
            paint_a = np.maximum(paint_a, solid_ai * struct)
        else:
            bridge = bridge_colour(ts, rgb1, tex, H, W, rng)
        painted = painted * (1 - struct[..., None]) + bridge * struct[..., None]
    ao = gaussian_filter(wh[..., 2], 6) * (0 if road else 1)
    damp = np.clip(gaussian_filter(wh[..., 3], 3) * 2, 0, 1)
    shadow_a = np.clip(0.26 * ao + 0.22 * damp, 0, 0.5) * land
    col = painted * (1 - 0.2 * damp * land)[..., None]

    # 5. Alpha: painted material over a shadow-only overlay; water transparent (the shader's HD water shows);
    #    missing cells fade out; specks of land in the water and pin-holes of water in the land cleaned up
    present = np.kron(np.array([[a1[y * 24:(y + 1) * 24, x * 24:(x + 1) * 24].any() for x in range(w_cells)]
                                for y in range(h_cells)], bool), np.ones((24 * SCALE, 24 * SCALE), bool))
    # (the template's outer border doesn't fade: the neighbouring template continues there with its own HD art)
    padded = np.pad(present, 1, mode="edge")
    edge = np.clip(distance_transform_edt(padded)[1:-1, 1:-1] / FEATHER, 0, 1)
    if road and TILESETS[ts].get("fade_roads"):
        border = distance_transform_edt(np.pad(present, 1, constant_values=False))[1:-1, 1:-1]
        wobble = gaussian_filter(rng.standard_normal((H, W)), 10, mode="wrap")
        wobble *= 10 / max(1e-6, wobble.std() * 2)
        edge = np.minimum(edge, smooth(border + wobble, *ROAD_FADE))
    solid = land > 0.5
    lab, n = label(solid)
    small_land = (np.bincount(lab.ravel()) < 160)[lab] & solid
    lab, n = label(~solid)
    small_water = (np.bincount(lab.ravel()) < 160)[lab] & ~solid
    land = np.where(small_land, 0, np.where(small_water, 1, land))
    land = gaussian_filter(land, 0.8)
    mat_a = paint_a * np.clip(land * 1.3 - 0.15, 0, 1)
    cover = mat_a + (1 - mat_a) * shadow_a
    alpha = cover * edge
    # shadow overlay is black (the edge fade scales colour and shadow alike, so it must not brighten the colour)
    col = col * (mat_a / np.maximum(cover, 1e-3))[..., None]
    rgba = np.dstack([np.clip(col, 0, 1), alpha])
    return (rgba * 255 + 0.5).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tileset", action="append", choices=sorted(TILESETS), help="default: all")
    ap.add_argument("--only", help="comma-separated template stems (e.g. s01,rv03)")
    ap.add_argument("--force", action="store_true", help="re-export the classic templates too")
    ap.add_argument("--preview", help="save a classic-vs-HD comparison sheet of the processed templates")
    ap.add_argument("--out", default=OUT, help="output folder (default: the mod's bits/hd/tiles)")
    args = ap.parse_args()

    preview = []
    for ts in args.tileset or sorted(TILESETS):
        templates = parse_templates(os.path.join(MOD, "tilesets", TILESETS[ts]["yaml"]), ts)
        if args.only:
            want = set(args.only.split(","))
            templates = [t for t in templates if stem(t) in want]
        ai = {os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(AI_TILES, ts, "*.png"))}
        templates = [t for t in templates if stem(t) not in ai or t.get("bridge_cells") or t.get("ramp")]
        classic = export_templates(ts, templates, args.force)
        textures = {k: load_texture(ts, k, REPEAT[k] * SCALE) for k in REPEAT}
        os.makedirs(os.path.join(args.out, ts), exist_ok=True)
        n = 0
        for t in templates:
            s = stem(t)
            if s not in classic:
                continue
            rng = np.random.default_rng(zlib.crc32(f"{ts}/{s}".encode()))
            t["ai"] = os.path.join(AI_TILES, ts, s + ".png") if s in ai else None
            hd = remaster(ts, t, classic[s], textures, rng)
            Image.fromarray(hd).save(os.path.join(args.out, ts, s + ".png"), optimize=True)
            n += 1
            if args.preview and len(preview) < 24:
                c = Image.fromarray((classic[s] * 255).astype(np.uint8)).resize((hd.shape[1], hd.shape[0]), Image.NEAREST)
                preview.append((c, Image.fromarray(hd)))
        print(f"{ts}: {n} templates -> {os.path.join(args.out, ts)}")

    if args.preview and preview:
        cw = max(c.width for c, _ in preview) * 2 + 24
        ch = max(c.height for c, _ in preview) + 12
        cols = 3
        rows = (len(preview) + cols - 1) // cols
        sheet = Image.new("RGBA", (cw * cols, ch * rows), (60, 70, 85, 255))
        for i, (c, h) in enumerate(preview):
            x, y = (i % cols) * cw, (i // cols) * ch
            sheet.alpha_composite(c.convert("RGBA"), (x, y))
            sheet.alpha_composite(h, (x + c.width + 8, y))
        sheet.save(args.preview)
        print("preview:", args.preview)


if __name__ == "__main__":
    main()
