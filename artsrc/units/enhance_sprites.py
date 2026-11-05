#!/usr/bin/env python3
"""Makes HD vehicle sprites read better at game size: calms the noisy AI camo texture, adds form shading
(large-radius local contrast), a little colour and a thin dark outline on the silhouette.

  python3 artsrc/units/enhance_sprites.py [<id> ...]        (from the repo root; no ids = all ground vehicles)
  python3 artsrc/units/enhance_sprites.py --restore [<id> ...]

The untouched render is kept in artsrc/units/sprites-orig/<id>.png and every run starts from it, so the
settings can be re-tuned without effects stacking. After a vehicle is re-rendered (meshes/make.sh) delete its
backup, then run this again. Run artsrc/fx/make_wreck_fx.py afterwards: wrecks are made from these sheets.
Only opaque body pixels are changed; the baked cast shadow (translucent) is left alone. Team-colour green keeps
its hue, so PlayerColorShift still recolours it.
"""
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageFilter, PngImagePlugin

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
UNITS = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "units")
BACKUP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites-orig")

VEHICLES = ["1tnk", "2tnk", "3tnk", "4tnk", "apc", "arty", "ctnk", "dtrk", "ftrk", "harv", "harvhalf", "harvempty",
            "hhusk", "hhusk2", "jeep", "mcv", "mgg", "mnly", "mrj", "ptnk", "truk", "ttnk", "v2rl"]

CALM = 0.6       # blend toward a 5px median: removes camo speckle, keeps panel edges
CONTRAST = 1.15  # global contrast around the body's mean brightness
LOCAL = 1.1      # local contrast at radius 7px: light and shadow sides of hull and turret
SATURATION = 1.1
OUTLINE = 0.6    # strength of the dark rim just inside the silhouette


def blur(x, radius):
    image = Image.fromarray((np.clip(x, 0, 1) * 255).astype(np.uint8))
    return np.asarray(image.filter(ImageFilter.GaussianBlur(radius))).astype(np.float32) / 255


def enhance(frame):
    a = np.asarray(frame).astype(np.float32) / 255
    rgb, alpha = a[..., :3], a[..., 3]
    body = alpha > 0.9
    if not body.any():
        return frame
    weights = np.array([0.299, 0.587, 0.114], dtype=np.float32)

    median = np.asarray(frame.convert("RGB").filter(ImageFilter.MedianFilter(5))).astype(np.float32) / 255
    calm = np.where(body[..., None], rgb * (1 - CALM) + median * CALM, rgb)
    lum = calm @ weights
    mean = lum[body].mean()
    target = mean + (lum - mean) * CONTRAST
    target = target + (target - blur(target, 7)) * LOCAL
    out = np.clip(calm * (np.clip(target, 0.01, 1.2) / np.maximum(lum, 0.01))[..., None], 0, 1)
    grey = (out @ weights)[..., None]
    out = np.clip(grey + (out - grey) * SATURATION, 0, 1)

    rim = np.clip((1 - blur(body.astype(np.float32), 2.2)) * 2.2, 0, 1) * OUTLINE
    out = out * (1 - rim[..., None] * 0.85)
    out = np.where(body[..., None], out, rgb)
    return Image.fromarray((np.dstack([out, alpha]) * 255 + 0.5).astype(np.uint8))


def process(unit):
    live = os.path.join(UNITS, unit + ".png")
    backup = os.path.join(BACKUP, unit + ".png")
    if not os.path.exists(backup):
        os.makedirs(BACKUP, exist_ok=True)
        shutil.copy2(live, backup)
    source = Image.open(backup)
    info = dict(source.info)
    sheet = source.convert("RGBA")
    fw, fh = map(int, info["FrameSize"].split(","))
    out = sheet.copy()
    for y in range(0, sheet.height - fh + 1, fh):
        for x in range(0, sheet.width - fw + 1, fw):
            out.paste(enhance(sheet.crop((x, y, x + fw, y + fh))), (x, y))
    # The engine needs the FrameSize/FrameAmount (and PxOffset) text chunks
    meta = PngImagePlugin.PngInfo()
    for key, value in info.items():
        if isinstance(value, str):
            meta.add_text(key, value)
    out.save(live, pnginfo=meta)
    print("enhanced", unit)


def restore(unit):
    backup = os.path.join(BACKUP, unit + ".png")
    if os.path.exists(backup):
        shutil.copy2(backup, os.path.join(UNITS, unit + ".png"))
        print("restored", unit)


def main():
    args = sys.argv[1:]
    action = process
    if args and args[0] == "--restore":
        action, args = restore, args[1:]
    for unit in args or VEHICLES:
        action(unit)


if __name__ == "__main__":
    main()
