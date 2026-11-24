"""
Walk cycle for a one-piece walker model (no rig): each leg's vertices bend about its hip with a smooth falloff,
the foot lifts on the forward swing, the body bobs and the trunk sways. Renders every facing x every step.

  Blender -b <unit>.blend -P artsrc/units/meshes/render_walk.py -- <unit> <out dir> [frame px] [samples]

Writes <out dir>/frame-NNN.png in the engine's order (facing * STEPS + step), for a sequence with Facings 32 and
Length STEPS. PX_WALK_FACINGS=8,4 renders only those facings (previews). Coordinates are the imported .blend's (Body at rest, nose +Y, ground z 0), in Blender units.

Elephanta (elph): a real elephant's lateral-sequence walk (left hind, left fore, right hind, right fore, a quarter
cycle apart), so three feet are always down.

Spider Tank (spdr): its legs are separate parts, so each leg turns as one rigid piece about its hip swivel (no
bending): a spider's alternating tetrapod gait, L1 R2 L3 R4 against R1 L2 R3 L4, half a cycle apart. A leg in swing
tilts up and sweeps forward, a leg in stance sweeps back on the ground. Only the hull is drawn (the turret sheet is
unchanged and sits on top), so the body does not bob. Pack at half resolution like the elephant (Scale 0.4667):
  python3 -c "import glob,PIL.Image as I;[I.open(f).resize((256,256),I.LANCZOS).save(f) for f in glob.glob('<out dir>/frame-*.png')]"
  python3 artsrc/units/pack_sprites.py <out dir> mods/rapx/bits/hd/units/spdr-walk.png 16
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
    # One cycle = 8 steps x 40 ms; with +-16 deg at ~3.3 units from the hip a stance sweeps ~1.8 units (~380 WDist),
    # close to Speed 70 x 8 ticks, so the feet barely slide.
    "spdr": {
        "steps": 8,
        "root": "Hull",
        "hide": ["Turret"],
        # leg -> phase; objects named Leg_<leg>_... (the Leg_mount_* parts stay on the body)
        "rigid_legs": {"left_front": 0.0, "right_side_front": 0.0, "left_side_rear": 0.0, "right_rear": 0.0,
                       "right_front": 0.5, "left_side_front": 0.5, "right_side_rear": 0.5, "left_rear": 0.5},
        "swing": 0.45,
        "angle": 16.0,        # degrees of sweep each side of the rest pose, about the hip's vertical axis
        "lift": 9.0,          # degrees the leg tilts up at mid-swing (foot ~0.5 units off the ground)
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


def rigid_legs(meshes, rest, cfg):
    """{object name: (pivot, outward unit vector, phase)} for the parts of each rigid leg."""
    legs = {}
    for leg, phase in cfg["rigid_legs"].items():
        parts = [o.name for o in meshes if o.name.startswith(f"Leg_{leg}_")]
        swivel = np.concatenate([rest[n][0] for n in parts if "_swivel" in n])
        foot = np.concatenate([rest[n][0] for n in parts if "_footpad" in n])
        pivot = (swivel.min(0) + swivel.max(0)) / 2
        out = foot.mean(0) - pivot
        out[2] = 0
        for n in parts:
            legs[n] = (pivot, out / np.linalg.norm(out), phase)
    return legs


def rotate(v, axis, angle):
    """Rodrigues rotation of rows v about the unit axis."""
    c, s = math.cos(angle), math.sin(angle)
    return v * c + np.cross(axis, v) * s + np.outer(v @ axis, axis) * (1 - c)


def pose_rigid(world, leg, cfg, p):
    pivot, out, phase = leg
    t = (p + phase) % 1.0
    a, s = math.radians(cfg["angle"]), cfg["swing"]
    if t < s:  # swing: up, back to front
        u = t / s
        yaw = -a + 2 * a * (0.5 - 0.5 * math.cos(math.pi * u))
        tilt = math.radians(cfg["lift"]) * math.sin(math.pi * u)
    else:  # stance: on the ground, front to back
        yaw, tilt = a - 2 * a * (t - s) / (1 - s), 0.0
    v = world - pivot
    v = rotate(v, np.cross(out, [0.0, 0.0, 1.0]), tilt)  # foot up
    # forward is +Y: a left leg (out -X) moves its foot forward turning clockwise, a right leg anticlockwise
    v = rotate(v, np.array([0.0, 0.0, 1.0]), -yaw if out[0] < 0 else yaw)
    return v + pivot


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
    root = bpy.data.objects[cfg.get("root", "Body")]
    for name in cfg.get("hide", []):
        for o in [bpy.data.objects[name], *bpy.data.objects[name].children_recursive]:
            o.hide_render = True
    render_sprites.face(root, 0, facings)
    bpy.context.view_layer.update()
    meshes = [o for o in root.children_recursive if o.type == "MESH"]
    rest = {}
    for o in meshes:
        co = np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", co)
        m = np.array(o.matrix_world)
        rest[o.name] = (co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3], np.linalg.inv(m))
    legs = rigid_legs(meshes, rest, cfg) if "rigid_legs" in cfg else None
    if legs is not None:
        meshes = [o for o in meshes if o.name in legs]

    for step in range(steps):
        render_sprites.face(root, 0, facings)
        for o in meshes:
            world, inv = rest[o.name]
            posed = pose_rigid(world, legs[o.name], cfg, step / steps) if legs else deform(world, cfg, step / steps)
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
