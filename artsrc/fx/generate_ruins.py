#!/usr/bin/env python3
"""
HD art for destroyed buildings (RedAlert Project X): asks ChatGPT (Codex CLI, artsrc/prompts/generate_images.py) for
the ruins a building leaves behind and a sheet of debris pieces, on flat magenta.

  python3 artsrc/fx/generate_ruins.py [names...]

Writes assets/fx/ruins/<name>.png (skips existing files). artsrc/fx/make_ruin_fx.py turns them into game sprites.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "prompts"))
import generate_images as gen  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "..", "assets", "fx", "ruins"))

RUIN = ("High-resolution photorealistic game asset: the burnt-out ruins of a destroyed {kind}, seen from a high-angle "
        "real-time strategy game camera (about 50 degrees down from the horizon), lying flat on the ground as an oval "
        "footprint about twice as wide as it is tall: a blackened, scorched patch of ground covered in {debris}, grey "
        "ash and a few faintly glowing embers, low rubble heaps in the middle, nothing standing taller than a low wall "
        "stump. The soot and ash thin out softly towards the edges. Isolated on a flat pure magenta (#FF00FF) "
        "background filling the rest of the image: no grass, no ground beyond the scorch, no shadow on the background, "
        "no smoke, no flames, no text, no border. Soft daylight from the top left. Landscape 3:2 image, the ruin filling "
        "most of the frame.")

PROMPTS = {
    "ruin-1": RUIN.format(kind="military factory building",
                          debris="broken concrete slabs, shattered bricks, twisted steel rebar, bent sheet metal and "
                                 "charred wooden beams"),
    "ruin-2": RUIN.format(kind="concrete barracks",
                          debris="broken concrete blocks, cracked floor slabs, crushed bricks, twisted rebar and burnt "
                                 "roof timbers"),
    "ruin-3": RUIN.format(kind="steel power plant",
                          debris="torn steel girders, crushed pipes, broken concrete, scattered bricks and scorched "
                                 "metal panels"),
    "debris": ("High-resolution photorealistic game sprite sheet: a grid of 4 columns and 2 rows, eight separate small "
               "pieces of building debris, one centred in each cell with wide empty gaps between them: a concrete "
               "chunk, a broken red brick, a short twisted piece of steel rebar, a charred wooden plank, a concrete "
               "slab corner with rebar sticking out, a bent piece of sheet metal, a lump of rubble, a burnt wooden "
               "beam end. Each piece seen from above at a 50 degree angle, each about the same size. Flat pure "
               "magenta (#FF00FF) background, no shadows, no text, no grid lines."),
}


def main():
    os.makedirs(OUT, exist_ok=True)
    names = sys.argv[1:] or list(PROMPTS)
    for name in names:
        dst = os.path.join(OUT, f"{name}.png")
        if os.path.exists(dst):
            print(f"{name}: exists, skipped")
            continue
        print(f"{name}: generating...", flush=True)
        src, err = gen.run_codex(PROMPTS[name], None, 600)
        if not src:
            print(f"{name}: FAILED\n{err}")
            continue
        shutil.copy(src, dst)
        print(f"{name}: {dst}", flush=True)


if __name__ == "__main__":
    main()
