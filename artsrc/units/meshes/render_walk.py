"""
Walk cycle for a one-piece walker model (no rig): each leg's vertices bend about its hip with a smooth falloff,
the foot lifts on the forward swing, the body bobs and the trunk sways. Renders every facing x every step.

  Blender -b <unit>.blend -P artsrc/units/meshes/render_walk.py -- <unit> <out dir> [frame px] [samples]

Writes <out dir>/frame-NNN.png in the engine's order (facing * STEPS + step), for a sequence with Facings 32 and
Length STEPS. PX_WALK_FACINGS=8,4 renders only those facings (previews). Coordinates are the imported .blend's (Body at rest, nose +Y, ground z 0), in Blender units.

Elephanta (elph): a real elephant's lateral-sequence walk (left hind, left fore, right hind, right fore, a quarter
cycle apart), so three feet are always down.
"""

import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import render_sprites  # noqa: E402

WALKS = {
    "elph": {
        "steps": 8,
        "hip": 3.5,           # hip height: the leg bends from here down
        "blend": 0.9,         # bend fades in over this height below the hip (no seam at the body)
        "half_width": 1.0,    # leg column: |x - cx| and |y - cy| within these
        "half_length": 1.45,
        # (cx, cy, phase): left hind, left fore, right hind, right fore
        "legs": [(-1.6, -2.7, 0.0), (-1.6, 0.85, 0.25), (1.5, -2.7, 0.5), (1.5, 0.85, 0.75)],
        "swing": 0.3,         # share of the cycle a foot is in the air
        "angle": 17.0,        # degrees each side of upright
        "lift": 0.45,         # foot lift at mid-swing
        "bob": 0.07,          # body rise and fall (twice a cycle)
        # trunk: verts with |x| < half_width, y > y0, z < z_top sway sideways, more towards the tip
        "trunk": {"half_width": 0.75, "y0": 2.3, "z_top": 5.6, "sway": 0.22},
    },
}


def smoothstep(e0, e1, v):
    t = np.clip((v - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def leg_pose(cfg, t):
    """Angle (radians, + = foot forward) and foot lift for a leg at cycle time t (0-1)."""
    a, s = math.radians(cfg["angle"]), cfg["swing"]
    if t < s:  # swing: back to front, in the air
        u = t / s
        return -a + 2 * a * (0.5 - 0.5 * math.cos(math.pi * u)), cfg["lift"] * math.sin(math.pi * u)
    u = (t - s) / (1 - s)  # stance: front to back on the ground, pushing the body forward
    return a - 2 * a * u, 0.0


def deform(rest, cfg, p):
    """Posed world coordinates of `rest` (N x 3) at cycle time p."""
    out = rest.copy()
    x, y, z = rest[:, 0], rest[:, 1], rest[:, 2]
    bend = smoothstep(cfg["hip"], cfg["hip"] - cfg["blend"], z)  # 0 at the hip, 1 down the leg
    on_leg = np.zeros(len(rest), bool)
    for cx, cy, phase in cfg["legs"]:
        sel = (np.abs(x - cx) < cfg["half_width"]) & (np.abs(y - cy) < cfg["half_length"]) & (z < cfg["hip"])
        on_leg |= sel
        angle, lift = leg_pose(cfg, (p + phase) % 1.0)
        th = angle * bend[sel]
        dy, dz = y[sel] - cy, z[sel] - cfg["hip"]
        out[sel, 1] = cy + dy * np.cos(th) - dz * np.sin(th)
        out[sel, 2] = cfg["hip"] + dy * np.sin(th) + dz * np.cos(th) + lift * smoothstep(cfg["hip"], 0.0, z[sel])
    # the body bobs (lowest when a foot lands); feet on the ground stay put
    bob = cfg["bob"] * math.cos(4 * math.pi * p)
    out[:, 2] += bob * np.where(on_leg, 1 - bend, 1.0)
    tr = cfg["trunk"]
    sel = (np.abs(x) < tr["half_width"]) & (y > tr["y0"]) & (z < tr["z_top"])
    out[sel, 0] += tr["sway"] * math.sin(2 * math.pi * p) * np.clip((tr["z_top"] - z[sel]) / tr["z_top"], 0, 1)
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    unit, out = argv[0], argv[1]
    frame = int(argv[2]) if len(argv) > 2 else 512
    samples = int(argv[3]) if len(argv) > 3 else 128
    cfg = WALKS[unit]
    steps, facings = cfg["steps"], 32
    only = [int(f) for f in os.environ.get("PX_WALK_FACINGS", "").split(",") if f]  # previews: these facings only

    render_sprites.setup(frame, samples)
    root = bpy.data.objects["Body"]
    render_sprites.face(root, 0, facings)
    bpy.context.view_layer.update()
    meshes = [o for o in root.children_recursive if o.type == "MESH"]
    rest = {}
    for o in meshes:
        co = np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", co)
        m = np.array(o.matrix_world)
        rest[o.name] = (co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3], np.linalg.inv(m))

    for step in range(steps):
        render_sprites.face(root, 0, facings)
        for o in meshes:
            world, inv = rest[o.name]
            posed = deform(world, cfg, step / steps)
            o.data.vertices.foreach_set("co", (posed @ inv[:3, :3].T + inv[:3, 3]).ravel())
            o.data.update()
        for f in only or range(facings):
            path = os.path.join(out, f"frame-{f * steps + step:03d}.png")
            if os.path.exists(path):  # resumable
                continue
            render_sprites.face(root, f, facings)
            render_sprites.render_to(path)
        print("step", step + 1, "of", steps, flush=True)


if __name__ == "__main__":
    main()
