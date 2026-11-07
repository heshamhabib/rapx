#!/usr/bin/env python3
"""
Our own chrono vortex lookup tables (IDEA-31): mods/rapx/bits/hole0000.lut ... hole0047.lut, read by the engine's
ChronoVortexRenderer for the vortex that plays when a chronoshifted construction yard returns. The originals came
from the game files.

Format (see engine/glsl/postprocess_textured_vortex.frag): per frame 64 x 64 pixels x 3 bytes. Bytes 1 and 2 are the
absolute x / y inside the 64x64 frame to sample the world from (a displacement), byte 3 darkens the result
(0..14 = 0.06..0.94 brightness; 255 = outside the vortex, pixel untouched). This draws a swirl that grows, twists
and collapses over 48 frames, darker towards its eye.

  python3 artsrc/sprites/make_vortex.py
"""
import math
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mods", "rapx", "bits")
N, FRAMES = 64, 48

for f in range(FRAMES):
    t = f / (FRAMES - 1)
    life = math.sin(math.pi * t)
    radius = 4 + 27 * math.sqrt(life)
    twist = 5.5 * life * (1 if t < 0.5 else 1.3)
    out = bytearray()
    for y in range(N):
        for x in range(N):
            dx, dy = x - 31.5, y - 31.5
            r = math.hypot(dx, dy)
            if r >= radius:
                out += bytes((x, y, 255))
                continue
            k = 1 - r / radius
            a = twist * k * k
            pull = 1 - 0.35 * life * k            # pulled towards the eye
            sx = 31.5 + (dx * math.cos(a) - dy * math.sin(a)) * pull
            sy = 31.5 + (dx * math.sin(a) + dy * math.cos(a)) * pull
            bright = 1 - 0.75 * life * k ** 1.6
            shade = max(0, min(14, round((bright - 0.0625) * 255 / 16)))
            out += bytes((max(0, min(255, round(sx))), max(0, min(255, round(sy))), shade))
    with open(os.path.join(OUT, f"hole{f:04d}.lut"), "wb") as fh:
        fh.write(out)
print(FRAMES, "frames ->", os.path.normpath(OUT))
