#!/usr/bin/env python3
"""
Measures how big units look in game: for a representative sequence of each actor image, the visible body
(alpha > 200, so soft shadows are ignored) of one frame, times the sequence Scale, in world pixels
(24 world px = one cell). Prints height on screen and longest extent.

  python3 artsrc/tools/measure_scale.py
"""
import os
import re

import numpy as np
from PIL import Image

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
MOD = os.path.join(ROOT, "mods", "rapx")
FILES = ["sequences/hd-units.yaml", "sequences/jets.yaml", "sequences/hd-infantry.yaml", "sequences/hd-soldiers3d.yaml",
         "sequences/prism.yaml", "sequences/hd-structures.yaml"]


def parse(files):
    """image -> seq -> {key: value} (Defaults merged), tab-indented MiniYaml, last definition wins."""
    out = {}
    for f in files:
        img = seq = None
        for line in open(os.path.join(MOD, f)):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            depth = len(line) - len(line.lstrip("\t"))
            key, _, val = line.strip().partition(":")
            if depth == 0:
                img = key
                out.setdefault(img, {})
            elif depth == 1:
                seq = key
                out[img].setdefault(seq, {})
            elif depth == 2 and img and seq:
                out[img][seq][key] = val.strip()
    for img, seqs in out.items():
        d = seqs.get("Defaults", {})
        for s, kv in seqs.items():
            for k, v in d.items():
                kv.setdefault(k, v)
    return out


def frame(path, index):
    im = Image.open(path)
    fw, fh = map(int, im.info.get("FrameSize", f"{im.width},{im.height}").split(","))
    cols = im.width // fw
    x, y = (index % cols) * fw, (index // cols) * fh
    return np.asarray(im.convert("RGBA").crop((x, y, x + fw, y + fh)))[..., 3]


def measure(seqs, img, seq, facing_frac=0.375):
    kv = seqs.get(img, {}).get(seq)
    if not kv or "Filename" not in kv:
        return None
    path = os.path.join(MOD, kv["Filename"].split("|", 1)[-1])
    if not path.endswith(".png") or not os.path.exists(path):
        return None
    scale = float(kv.get("Scale", 1))
    facings = int(kv.get("Facings", 1))
    length = int(kv.get("Length", 1)) if kv.get("Length", "1").isdigit() else 1
    stride = int(kv.get("Stride", length)) if kv.get("Stride", "").isdigit() else length
    start = int(kv.get("Start", 0))
    # a three-quarter facing (south-west-ish), same view for every unit
    f = int(round(facing_frac * facings)) % facings if facings > 1 else 0
    a = frame(path, start + f * stride)
    ys, xs = np.nonzero(a > 200)
    if not len(xs):
        return None
    h = (ys.max() - ys.min() + 1) * scale
    w = (xs.max() - xs.min() + 1) * scale
    return h, w


UNITS = [
    ("Soldier (3D) Rifle Infantry", "e1", "stand"), ("Soldier (AI) Rocket Soldier", "e3", "stand"),
    ("Soldier (AI) Tanya", "e7", "stand"), ("Attack Dog", "dog", "stand"),
    ("Cyborg Trooper", "cybt", "stand"), ("Battle Droid", "bdrd", "stand"), ("Iron Guard", "irgd", "stand"),
    ("Enforcer Walker", "enfw", "stand"), ("Strider", "strd", "stand"), ("Spider Drone", "sdrn", "stand"),
    ("Jeep", "jeep", "idle"), ("APC", "apc", "idle"), ("Light Tank", "1tnk", "idle"), ("Medium Tank", "2tnk", "idle"),
    ("Heavy Tank", "3tnk", "idle"), ("Mammoth Tank", "4tnk", "idle"), ("Prism Tank", "ptnk", "idle"),
    ("Artillery", "arty", "idle"), ("Ore Truck", "harv", "idle"), ("MCV", "mcv", "idle"),
    ("Jet F-16", "jet.f16", "idle"), ("Jet F-14", "jet.f14", "idle"), ("Jet A-10", "jet.a10", "idle"),
    ("Construction Yard (3x3)", "fact", "idle"), ("Power Plant (2x2)", "powr", "idle"), ("Barracks (2x2)", "tent", "idle"),
    ("War Factory (3x3)", "weap", "idle"), ("Pillbox (1x1)", "pbox", "idle"),
]

if __name__ == "__main__":
    seqs = parse(FILES)
    print(f"{'unit':34s} {'height':>7s} {'extent':>7s}   (world px; 24 = one cell)")
    for name, img, seq in UNITS:
        m = measure(seqs, img, seq)
        print(f"{name:34s} " + (f"{m[0]:7.1f} {m[1]:7.1f}" if m else "    n/a"))
