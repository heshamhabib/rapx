#!/usr/bin/env python3
"""Builds the per-language fonts in mods/rapx/fonts/lang from Google Fonts (OFL) sources.

  python3 artsrc/lang-fonts/make_fonts.py <dir with the downloaded sources>

Sources (github.com/google/fonts, ofl/): changa/Changa[wght].ttf, sairasemicondensed/SairaSemiCondensed-{Medium,SemiBold,Bold}.ttf,
notosanssc/NotoSansSC[wght].ttf. Variable fonts are pinned to static weights (OpenRA's FreeType path ignores
variations). Noto Sans SC is cut down to GB2312 + every character in the zh translation so it stays a few MB.
"""
import glob
import os
import shutil
import sys

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "mods/rapx/fonts/lang")
WEIGHTS = {"Medium": 500, "SemiBold": 600, "Bold": 700}


def pin(src, wght, dst):
    font = instancer.instantiateVariableFont(TTFont(src), {"wght": wght})
    font.save(dst)


def gb2312():
    chars = set()
    for hi in range(0xA1, 0xF8):
        for lo in range(0xA1, 0xFF):
            try:
                chars.add(bytes([hi, lo]).decode("gb2312"))
            except UnicodeDecodeError:
                pass
    return chars


def subset_cjk(path, chars):
    font = TTFont(path)
    opts = subset.Options()
    opts.layout_features = []
    opts.hinting = False
    opts.name_IDs = ["*"]
    sub = subset.Subsetter(opts)
    sub.populate(text="".join(sorted(chars)))
    sub.subset(font)
    font.save(path)


def main():
    src = sys.argv[1]
    os.makedirs(OUT, exist_ok=True)
    for name, wght in WEIGHTS.items():
        pin(os.path.join(src, "Changa[wght].ttf"), wght, os.path.join(OUT, f"Changa-{name}.ttf"))
        shutil.copy(os.path.join(src, f"SairaSemiCondensed-{name}.ttf"), os.path.join(OUT, f"SairaSemiCondensed-{name}.ttf"))

    chars = gb2312() | {chr(c) for c in range(0x20, 0x7F)} | set("，。！？：；“”‘’（）《》、…—·￥％")
    for ftl in glob.glob(os.path.join(ROOT, "mods/rapx/fluent/lang/zh/*.ftl")):
        chars |= set(open(ftl, encoding="utf-8").read())

    for name in ("Medium", "Bold"):
        dst = os.path.join(OUT, f"NotoSansSC-{name}.ttf")
        pin(os.path.join(src, "NotoSansSC[wght].ttf"), WEIGHTS[name], dst)
        subset_cjk(dst, chars)

    for lic in ("Changa", "SairaSemiCondensed", "NotoSansSC"):
        shutil.copy(os.path.join(src, f"{lic}-OFL.txt"), os.path.join(OUT, f"{lic}-OFL.txt"))

    for f in sorted(os.listdir(OUT)):
        print(f, os.path.getsize(os.path.join(OUT, f)) // 1024, "KB")


if __name__ == "__main__":
    main()
