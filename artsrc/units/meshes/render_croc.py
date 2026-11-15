"""
Animates the Nile Crocodile (croc: one static Sketchfab mesh, no rig) by bending its vertices, and renders every
sequence the infantry body needs. Poses follow a real crocodile:

  walk   the "high walk": diagonal legs move together (left fore + right hind, then the other pair), the sprawled
         legs swing forwards and back around the shoulders and lift on the swing, and an S-wave runs down the body
         to the tail
  swim   legs folded back along the flanks, the tail sculls in big waves; sunk to the eyes (everything below the
         waterline, z 0, is transparent)
  idle   lying still, slowly gaping (crocodiles cool off with the jaws open), the tail tip twitching
  bite   the head lunges, the jaws open wide, snap shut, and the head shakes the prey
  die    rolls over onto its back (one facing, like the dog's deaths)

  Blender -b croc.blend -P artsrc/units/meshes/render_croc.py -- <out dir> [anim ...]
  env PX_CROC_FACINGS=8 (previews: these facings only), PX_SAMPLES (default 64), PX_LIGHT/PX_UNIT_PX as make_sketchfab

Writes <out dir>/<anim>/frame-NNN.png, facing-major (facing * steps + step), for packing with pack_sprites.py.
Coordinates: the imported .blend (Body at rest, nose +Y, ground z 0), measured as fractions of the length (u: 0 tail
tip, 1 nose) so the poses do not depend on the model's size.
"""

import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import render_sprites  # noqa: E402

FRAME = 256
STEPS = {"walk": 8, "swim": 8, "idle": 8, "bite": 6, "die": 10}
DIE_FACING = 6

# Body plan (fractions of the length; from the mesh profile)
FORE = 0.80          # front shoulders (u)
HIND = 0.555         # hips (u)
LEG_U = 0.075        # each leg reaches this far along u from its shoulder
SHOULDER_X = 0.07    # |x| / length where the legs leave the body
HINGE_U = 0.865      # jaw hinge (u)
MOUTH_H = 0.42       # mouth line height (fraction of the model height)
HEAD_U = 0.85        # the head starts here


def smoothstep(e0, e1, v):
    t = np.clip((v - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


class Croc:
    def __init__(self, rest):
        self.rest = rest
        x, y, z = rest.T
        self.y0, self.length = y.min(), y.max() - y.min()
        self.height = z.max()
        self.u = (y - self.y0) / self.length
        self.ax = np.abs(x) / self.length
        L = self.length
        self.legs = []  # (mask, shoulder x, shoulder y, side, pair phase)
        for centre, fore in ((FORE, True), (HIND, False)):
            for side in (-1, 1):
                mask = (np.abs(self.u - centre) < LEG_U) & (self.ax > SHOULDER_X * 0.9) & (np.sign(x) == side)
                # walking pairs: left fore + right hind, right fore + left hind
                phase = 0.0 if (side < 0) == fore else 0.5
                self.legs.append((mask, side * SHOULDER_X * L, self.y0 + centre * L, side, phase))
        self.leg_weight = smoothstep(SHOULDER_X, SHOULDER_X + 0.05, self.ax)

    def wave(self, out, p, amp_head, amp_tail, cycles):
        """S-wave down the body: sideways offset growing towards the tail, travelling from head to tail."""
        u = self.u
        amp = self.length * (amp_head + amp_tail * (1 - u) ** 2)
        out[:, 0] += amp * np.sin(2 * math.pi * (p - cycles * (1 - u)))

    def swing_legs(self, out, angle_of, lift_of):
        """Turns each leg around its shoulder (about z): angle_of(leg index) radians, + = foot forwards."""
        for i, (mask, sx, sy, side, phase) in enumerate(self.legs):
            th = side * angle_of(i, phase) * self.leg_weight[mask]
            dx, dy = out[mask, 0] - sx, out[mask, 1] - sy
            out[mask, 0] = sx + dx * np.cos(th) - dy * np.sin(th)
            out[mask, 1] = sy + dx * np.sin(th) + dy * np.cos(th)
            reach = np.clip((self.ax[mask] - SHOULDER_X) / 0.12, 0, 1)
            out[mask, 2] += lift_of(i, phase) * self.length * reach

    def jaws(self, out, open_deg, lunge=0.0, shake=0.0):
        """Lower jaw down by open_deg about the hinge, upper head up a third of that; head forward and sideways."""
        L, H = self.length, self.height
        hy, hz = self.y0 + HINGE_U * L, MOUTH_H * H
        w = smoothstep(HINGE_U - 0.02, HINGE_U + 0.01, self.u)
        lower = self.rest[:, 2] < hz
        for sel, deg in ((lower, -open_deg), (~lower, open_deg / 3)):
            m = sel & (w > 0)
            th = math.radians(deg) * w[m]
            dy, dz = out[m, 1] - hy, out[m, 2] - hz
            out[m, 1] = hy + dy * np.cos(th) - dz * np.sin(th)
            out[m, 2] = hz + dy * np.sin(th) + dz * np.cos(th)
        neck = smoothstep(0.62, HEAD_U, self.u)
        out[:, 1] += lunge * L * neck
        out[:, 0] += shake * L * neck ** 2

    def pose(self, anim, step):
        out = self.rest.copy()
        n = STEPS[anim]
        p = step / n
        if anim == "walk":
            def angle(i, phase):
                t = (p + phase) % 1.0
                a = math.radians(26)
                if t < 0.4:  # swing: back to front
                    return -a + 2 * a * (0.5 - 0.5 * math.cos(math.pi * t / 0.4))
                return a - 2 * a * (t - 0.4) / 0.6

            def lift(i, phase):
                t = (p + phase) % 1.0
                return 0.035 * math.sin(math.pi * t / 0.4) if t < 0.4 else 0.0
            self.swing_legs(out, angle, lift)
            self.wave(out, p, 0.004, 0.045, 0.8)
            out[:, 2] += self.length * 0.004 * math.cos(4 * math.pi * p)
        elif anim == "swim":
            self.swing_legs(out, lambda i, ph: -math.radians(55), lambda i, ph: 0.0)  # folded back
            self.wave(out, p, 0.003, 0.09, 1.0)
            out[:, 2] -= 0.55 * self.height  # sunk to the eyes
        elif anim == "idle":
            gape = 22 * math.sin(math.pi * p) ** 2
            self.jaws(out, gape)
            u = self.u
            out[:, 0] += self.length * 0.02 * smoothstep(0.25, 0.0, u) * math.sin(2 * math.pi * p)
            out[:, 2] += self.length * 0.002 * math.sin(2 * math.pi * p) * smoothstep(0.4, 0.6, u)
        elif anim == "bite":
            lunge = [0.0, 0.03, 0.09, 0.1, 0.07, 0.03][step]
            gape = [10, 30, 42, 0, 0, 0][step]
            shake = [0, 0, 0, 0.0, 0.035, -0.035][step]
            self.jaws(out, gape, lunge, shake)
            self.wave(out, p, 0.0, 0.05 if step >= 3 else 0.0, 0.5)
        elif anim == "die":
            t = smoothstep(0.0, 0.7, np.array(p))
            self.swing_legs(out, lambda i, ph: math.radians(20) * t, lambda i, ph: 0.02 * t)
            roll = math.radians(165) * t
            cz = self.height * 0.5
            x, z = out[:, 0].copy(), out[:, 2] - cz
            out[:, 0] = x * math.cos(roll) - z * math.sin(roll)
            out[:, 2] = cz + x * math.sin(roll) + z * math.cos(roll)
            out[:, 2] -= out[:, 2].min()  # rest on the ground
        return out


def waterline(materials):
    """Everything below z 0 renders transparent (the swim frames: sunk in the water)."""
    for mat in materials:
        nt = mat.node_tree
        output = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
        link = output.inputs["Surface"].links[0]
        shader = link.from_socket
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        less = nt.nodes.new("ShaderNodeMath")
        less.operation = "LESS_THAN"
        less.inputs[1].default_value = 0.0
        clear = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(geo.outputs["Position"], sep.inputs[0])
        nt.links.new(sep.outputs["Z"], less.inputs[0])
        nt.links.new(less.outputs[0], mix.inputs[0])
        nt.links.new(shader, mix.inputs[1])
        nt.links.new(clear.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], output.inputs["Surface"])


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = argv[0]
    anims = argv[1:] or list(STEPS)
    only = [int(f) for f in os.environ.get("PX_CROC_FACINGS", "").split(",") if f]
    render_sprites.setup(FRAME, int(os.environ.get("PX_SAMPLES", "64")))
    root = bpy.data.objects["Body"]
    render_sprites.face(root, 0, 32)
    bpy.context.view_layer.update()
    meshes = [o for o in root.children_recursive if o.type == "MESH"]
    worlds, invs, sizes = [], [], []
    for o in meshes:
        co = np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", co)
        m = np.array(o.matrix_world)
        worlds.append(co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3])
        invs.append(np.linalg.inv(m))
        sizes.append(len(o.data.vertices))
    croc = Croc(np.vstack(worlds))
    rest_local = [w.copy() for w in worlds]
    water_set = False

    for anim in anims:
        if anim == "swim" and not water_set:
            waterline({s.material for o in meshes for s in o.material_slots if s.material})
            water_set = True
        steps = STEPS[anim]
        facings = [DIE_FACING] if anim == "die" else (only or range(32))
        for step in range(steps):
            posed = croc.pose(anim, step)
            start = 0
            for o, inv, n in zip(meshes, invs, sizes):
                part = posed[start:start + n]
                start += n
                o.data.vertices.foreach_set("co", (part @ inv[:3, :3].T + inv[:3, 3]).ravel())
                o.data.update()
            for f in facings:
                index = step if anim == "die" else f * steps + step
                path = os.path.join(out, anim, f"frame-{index:03d}.png")
                if os.path.exists(path):  # resumable
                    continue
                render_sprites.face(root, f, 32)
                render_sprites.render_to(path)
        print(anim, "done", flush=True)
    for o, w, inv in zip(meshes, rest_local, invs):
        o.data.vertices.foreach_set("co", (w @ inv[:3, :3].T + inv[:3, 3]).ravel())


if __name__ == "__main__":
    main()
