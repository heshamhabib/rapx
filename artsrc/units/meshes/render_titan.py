"""
Titans (lobby choice, rules/titans.yaml): imports a rigged Sketchfab giant, poses its own skeleton for every sequence
and renders the frames with the HD light. No animation comes with the models; the poses are made here.

  Blender -b -P artsrc/units/meshes/render_titan.py -- <titan> <out dir> [anim ...]
  env PX_TITAN_FACINGS=0,4 / PX_TITAN_STEPS=0,4 (previews: only these), PX_SAMPLES (default 48)

  godz   Godzilla ("Evolved Godzilla" by savounited, CC-BY-4.0): a heavy biped walk with the tail swaying behind;
         shoot = atomic breath: the head rears back while the dorsal plates light up (pink, like the model's plates),
         then the jaws open wide and the head thrusts forward; die = falls onto its side; swim = sunk to the
         shoulders (everything below the water line, z 0, is transparent), only the head and the plates show while
         the legs paddle and the tail sculls in big waves. Render swim last: the water line stays on the materials
  kong   Kong ("King Kong 2005" by sharksly, CC-BY-4.0): an upright, hunched ape walk with swinging arms;
         shoot = double-fist hammer blow overhead; throw = boulder throw with the right arm; die = falls backwards;
         jump = anti-air leap: crouch, spring up with both arms overhead, swat at the top (frame 3), drop and land

  art    (anim name) lobby art for artsrc/px-ui/make_titan_art.py: a hero pose (Godzilla mid-breath with his plates
         lit, Kong roaring with his arms down at his sides) from a low three-quarter angle, as a wide banner (whole body) and a close
         portrait (head and shoulders), transparent, into artsrc/px-ui/titans/<titan>-{banner,portrait}.png
  cameo  (anim name) the catalogue / tile cameo: idle pose, front-left side, low three-quarter camera, tightly
         framed, no ground, written to assets/units/renders/<titan>.png for artsrc/px-cameos/generate.py

Writes <out dir>/<anim>/frame-NNN.png facing-major (facing * steps + step; die: one facing) for pack_trimmed.py.
Frames are rendered at half the vehicle density (PX_UNIT_PX 3.5), so the sequences use Scale 0.4667 like elph-walk.
All bone moves are rotations about world axes through the bone's head (nose +Y, up +Z), so the models' own bone
axes do not matter.
"""

import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import render_sprites  # noqa: E402

# Godzilla's snout in the breath pose (shoot step 5, facing 0, render units): measured from the posed mesh and checked
# with a marker render. rules/titans.yaml PxTitanArmament uses the same point (x 209.07 WDist per unit).
MOUTH = (0.0, 13.0, 12.8)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_croc import waterline  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FACINGS = 16
DIE_FACING = 3

TITANS = {
    # Godzilla turns slowly and is the biggest thing on screen: 32 facings so he turns smoothly (Kong: 16). His frame is
    # 704: at 352 the raised head (242 px above centre) and the swung tail (315 px right) were cut off.
    # Water: dive (wading in, sinking to the shoulders) and emerge play between walk and swim (render them last,
    # after swim: the water line stays on the materials).
    "godz": {"src": "titans/godzilla/scene.gltf", "yaw": 180, "length": 26.0, "frame": 704, "facings": 32,
             "steps": {"idle": 8, "walk": 8, "shoot": 8, "die": 12, "swim": 8, "dive": 6, "emerge": 6},
             "glow": (1.0, 0.12, 0.6), "glow_axis": (2.27, -0.69), "frames": {"die": 560}},
    "kong": {"src": "titans/kong/scene.gltf", "yaw": 180, "height": 14.0, "frame": 352,
             "steps": {"idle": 8, "walk": 8, "shoot": 6, "throw": 6, "die": 12, "jump": 8},
             "frames": {"jump": 512, "die": 512}},  # room above him for the leap, and around the fallen body
}

X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


def find(arm, *needles):
    """The first pose bone whose name contains every needle (case-insensitive)."""
    for pb in arm.pose.bones:
        n = pb.name.lower()
        if all(s in n for s in needles):
            return pb
    raise KeyError(needles)


class Rig:
    def __init__(self, arm):
        self.arm = arm
        # The pose stored in the file (Kong's bones hold his standing pose; their rest is lying down)
        self.base = {pb.name: pb.matrix_basis.copy() for pb in arm.pose.bones}

    def reset(self):
        for pb in self.arm.pose.bones:
            pb.matrix_basis = self.base[pb.name]
        bpy.context.view_layer.update()

    def rot(self, pb, axis, deg):
        """Turns a bone (and so its children) about a world axis through its head."""
        if not deg:
            return
        mw = self.arm.matrix_world
        cur = mw @ pb.matrix
        head = cur.to_translation()
        r = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-head)
        pb.matrix = mw.inverted() @ r @ cur
        bpy.context.view_layer.update()

    def move(self, pb, offset):
        mw = self.arm.matrix_world
        cur = mw @ pb.matrix
        pb.matrix = mw.inverted() @ (Matrix.Translation(offset) @ cur)
        bpy.context.view_layer.update()


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


# --- Godzilla -----------------------------------------------------------------------------------------------------

class Godzilla(Rig):
    def __init__(self, arm):
        super().__init__(arm)
        self.pelvis = find(arm, "bip_pelvis")
        self.hips = [find(arm, "bip_hip_l"), find(arm, "bip_hip_r")]
        self.knees = [find(arm, "bip_knee_l"), find(arm, "bip_knee_r")]
        self.feet = [find(arm, "bip_foot_l"), find(arm, "bip_foot_r")]
        self.tail = [find(arm, "bip_tail_35")] + [find(arm, f"bip_tail_{i}_") for i in range(1, 8)]
        self.spine = [find(arm, "bip_spine_0"), find(arm, "bip_spine_1"), find(arm, "bip_spine_2")]
        self.neck = [find(arm, "bip_neck_91"), find(arm, "bip_neck_1")]
        self.head = find(arm, "bip_head")
        self.jaw = find(arm, "bip_jaw")
        self.upper_arms = [find(arm, "bip_upperarm_l"), find(arm, "bip_upperarm_r")]

    def tail_wave(self, p, amp, lift=0.0):
        for i, b in enumerate(self.tail):
            self.rot(b, Z, amp * (0.4 + 0.15 * i) * math.sin(2 * math.pi * p - 0.55 * i))
            if lift:
                self.rot(b, X, lift)

    def pose(self, anim, step, n):
        self.reset()
        p = step / n
        if anim == "walk":
            # One stride per leg per cycle; the body rolls over the planted foot
            for side, (hip, knee, foot) in enumerate(zip(self.hips, self.knees, self.feet)):
                ph = 2 * math.pi * (p + 0.5 * side)
                self.rot(hip, X, 24 * math.sin(ph))
                bend = max(0.0, math.cos(ph))  # swing phase: the knee folds to lift the foot
                self.rot(knee, X, -30 * bend)
                self.rot(foot, X, 18 * bend)
            self.rot(self.pelvis, Y, 4 * math.sin(2 * math.pi * p))
            self.move(self.pelvis, Vector((0, 0, 0.012 * abs(math.cos(2 * math.pi * p)))))
            for i, ua in enumerate(self.upper_arms):
                self.rot(ua, X, 10 * math.sin(2 * math.pi * p + math.pi * (1 - i)))
            self.rot(self.spine[1], Z, -3 * math.sin(2 * math.pi * p))
            self.rot(self.head, X, 3 * math.cos(4 * math.pi * p))
            self.tail_wave(p, 5)
        elif anim == "idle":
            breathe = math.sin(2 * math.pi * p)
            self.rot(self.spine[2], X, 1.5 * breathe)
            self.rot(self.neck[0], Z, 6 * math.sin(2 * math.pi * p))
            self.rot(self.head, X, -2 * breathe)
            self.tail_wave(p, 3)
        elif anim == "shoot":
            # 0-3: rear back and charge (plates light up); 4-7: jaws wide, head thrust forward
            charge = ease(step / 3) if step < 4 else 1.0
            fire = ease((step - 3) / 2) if step >= 4 else 0.0
            self.rot(self.spine[1], X, 10 * charge - 14 * fire)
            self.rot(self.neck[0], X, 14 * charge - 24 * fire)
            self.rot(self.head, X, 8 * charge - 10 * fire)
            self.rot(self.jaw, X, -35 * fire)
            for ua in self.upper_arms:
                self.rot(ua, X, -15 * charge)
            self.tail_wave(p, 2, lift=-2 * charge)
        elif anim in ("dive", "emerge"):
            # Wading in (or out): the walk keeps going while he leans into the water and sinks to the shoulders
            t = ease(step / (n - 1))
            if anim == "emerge":
                t = 1 - t
            for side, (hip, knee, foot) in enumerate(zip(self.hips, self.knees, self.feet)):
                ph = 2 * math.pi * (p + 0.5 * side)
                self.rot(hip, X, (24 - 6 * t) * math.sin(ph))
                bend = max(0.0, math.cos(ph))
                self.rot(knee, X, -30 * bend)
                self.rot(foot, X, 18 * bend)
            self.rot(self.spine[0], X, -12 * t)
            self.rot(self.neck[0], X, 10 * t)
            self.rot(self.spine[1], Z, -3 * math.sin(2 * math.pi * p))
            self.tail_wave(p, 5 + 5 * t)
            return {"glow": 0.0, "fall": None, "sink": 0.52 * t}
        elif anim == "swim":
            for side, (hip, knee) in enumerate(zip(self.hips, self.knees)):
                ph = 2 * math.pi * (p + 0.5 * side)
                self.rot(hip, X, 18 * math.sin(ph))
                self.rot(knee, X, -20 * max(0.0, math.cos(ph)))
            for side, ua in enumerate(self.upper_arms):
                self.rot(ua, X, 25 * math.sin(2 * math.pi * p + math.pi * side))
            self.rot(self.spine[0], X, -12)  # leaning into the water, head up
            self.rot(self.neck[0], X, 10)
            self.rot(self.spine[1], Z, 4 * math.sin(2 * math.pi * p))
            self.tail_wave(p, 10)
            return {"glow": 0.0, "fall": None, "sink": 0.52}
        elif anim == "die":
            t = ease(step / (n - 3))
            self.rot(self.neck[0], X, -25 * t)
            self.rot(self.jaw, X, -20 * t)
            for ua in self.upper_arms:
                self.rot(ua, X, 30 * t)
            self.tail_wave(0.25, 4 * t)
        return {"glow": self.glow(anim, step), "fall": (Y, 88 * ease(step / (n - 3))) if anim == "die" else None}

    @staticmethod
    def glow(anim, step):
        """(strength, wave): the plates light up in a wave from the tail tip (0) to the head (1) while he charges,
        and stay lit while the beam fires. Also returns whether the mouth glows."""
        if anim == "shoot":
            return ([1.6, 2.0, 2.3, 2.6, 2.8, 2.7, 2.4, 2.0][step], [0.2, 0.5, 0.8, 1.15, 1.15, 1.15, 1.15, 1.15][step],
                    step >= 3)
        return (0.0, 0.0, False)


# --- Kong ---------------------------------------------------------------------------------------------------------

class Kong(Rig):
    def __init__(self, arm):
        super().__init__(arm)
        self.pelvis = find(arm, "pelvis")
        self.thighs = [find(arm, "leg left thigh"), find(arm, "leg right thigh")]
        self.knees = [find(arm, "leg left knee"), find(arm, "leg right knee")]
        self.ankles = [find(arm, "leg left ankle"), find(arm, "leg right ankle")]
        self.spine = [find(arm, "spine lower"), find(arm, "spine upper")]
        self.neck = find(arm, "head neck lower")
        self.head = find(arm, "head neck upper")
        self.jaw = find(arm, "head jaw")
        self.shoulders = [find(arm, "arm left shoulder 2"), find(arm, "arm right shoulder 2")]
        self.elbows = [find(arm, "arm left elbow"), find(arm, "arm right elbow")]

    def stance(self, hunch=14):
        """From the model's A-pose: arms hanging down by the sides, the back hunched forward."""
        self.rot(self.spine[0], X, -hunch)
        self.rot(self.neck, X, hunch * 0.8)
        for side, sh in enumerate(self.shoulders):
            s = -1 if side == 0 else 1  # after the 180° yaw his left arm points -X
            self.rot(sh, Y, s * 48)
            self.rot(sh, X, 8)

    def pose(self, anim, step, n):
        self.reset()
        p = step / n
        if anim == "walk":
            self.stance()
            for side, (th, kn, an) in enumerate(zip(self.thighs, self.knees, self.ankles)):
                ph = 2 * math.pi * (p + 0.5 * side)
                self.rot(th, X, 26 * math.sin(ph))
                bend = max(0.0, math.cos(ph))
                self.rot(kn, X, -32 * bend)
                self.rot(an, X, 14 * bend)
            for side, (sh, el) in enumerate(zip(self.shoulders, self.elbows)):
                ph = 2 * math.pi * (p + 0.5 * (1 - side))
                self.rot(sh, X, 28 * math.sin(ph))
                self.rot(el, X, 12 + 10 * max(0.0, math.sin(ph)))
            self.rot(self.spine[0], Z, 5 * math.sin(2 * math.pi * p))
            self.rot(self.pelvis, Y, 3 * math.sin(2 * math.pi * p))
            self.move(self.pelvis, Vector((0, 0, 0.1 * abs(math.cos(2 * math.pi * p)))))
        elif anim == "idle":
            self.stance(12 + 2 * math.sin(2 * math.pi * p))
            self.rot(self.head, Z, 10 * math.sin(2 * math.pi * p))
        elif anim == "shoot":
            # Double-fist hammer: arms swing up over the head (0-2), then smash down in front (3-5)
            self.stance()
            up = [0.3, 0.75, 1.0, 0.6, 0.0, 0.0][step]
            down = [0.0, 0.0, 0.0, 0.5, 1.0, 1.0][step]
            self.rot(self.spine[0], X, 10 * up - 22 * down)
            for side, (sh, el) in enumerate(zip(self.shoulders, self.elbows)):
                s = -1 if side == 0 else 1
                self.rot(sh, Y, -s * 30 * up)
                self.rot(sh, X, 150 * up + 60 * down)
                self.rot(el, X, 25 * up)
            self.rot(self.jaw, X, -25 * up)
        elif anim == "throw":
            # Right arm: wind back (0-2), sling the boulder forward overhand (3-5)
            self.stance()
            back = [0.4, 0.8, 1.0, 0.3, 0.0, 0.0][step]
            fwd = [0.0, 0.0, 0.0, 0.6, 1.0, 0.7][step]
            sh, el = self.shoulders[1], self.elbows[1]
            self.rot(self.spine[0], Z, -18 * back + 16 * fwd)
            self.rot(sh, X, -60 * back + 140 * fwd)
            self.rot(sh, Y, 20 * back)
            self.rot(el, X, 40 * back)
            self.rot(self.jaw, X, -20 * fwd)
        elif anim == "roar":
            # Lobby art: standing tall in his stance, arms down at his sides, head up, jaws wide
            self.stance(8)
            for side, (sh, el) in enumerate(zip(self.shoulders, self.elbows)):
                s = -1 if side == 0 else 1
                self.rot(sh, Y, s * 8)
                self.rot(sh, X, 12)
                self.rot(el, X, 25)
            self.rot(self.neck, X, 12)
            self.rot(self.head, X, 10)
            self.rot(self.jaw, X, -50)
            return {"glow": 0.0, "fall": None}
        elif anim == "jump":
            # crouch, launch, apex swat (3-4), fall, land, recover; lift = fraction of his height off the ground
            lift = [0.0, 0.0, 0.35, 0.62, 0.6, 0.32, 0.0, 0.0][step]
            crouch = [0.6, 1.0, 0.2, 0.0, 0.0, 0.1, 1.0, 0.4][step]
            reach = [0.0, -0.3, 0.8, 1.0, 0.7, 0.3, 0.0, 0.0][step]
            swat = [0.0, 0.0, 0.0, 0.3, 1.0, 0.6, 0.0, 0.0][step]
            self.stance(14 + 16 * crouch)
            for side, (th, kn, an) in enumerate(zip(self.thighs, self.knees, self.ankles)):
                self.rot(th, X, 35 * crouch - 10 * (lift > 0))
                self.rot(kn, X, -60 * crouch + 15 * (lift > 0))
                self.rot(an, X, 25 * crouch)
            for side, (sh, el) in enumerate(zip(self.shoulders, self.elbows)):
                s = -1 if side == 0 else 1
                self.rot(sh, Y, -s * 35 * max(reach, 0))
                self.rot(sh, X, 165 * max(reach, 0) - 30 * min(reach, 0) - 70 * swat)
                self.rot(el, X, 20 * reach)
            self.rot(self.spine[0], Z, 25 * swat)
            self.rot(self.jaw, X, -28 * max(reach, 0))
            self.rot(self.head, X, 25 * reach)  # looking up at the aircraft
            return {"glow": 0.0, "fall": None, "lift": lift}
        elif anim == "die":
            t = ease(step / (n - 3))
            self.stance(14 * (1 - t))
            for sh in self.shoulders:
                self.rot(sh, X, 40 * t)
            self.rot(self.jaw, X, -20 * t)
        return {"glow": 0.0, "fall": (X, 85 * ease(step / (n - 3))) if anim == "die" else None}


# --- Scene --------------------------------------------------------------------------------------------------------

def import_titan(name, cfg):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.join(HERE, "glb", "sketchfab", cfg["src"]))
    for o in list(bpy.data.objects):
        if o.name.startswith("Icosphere"):  # a stray helper sphere in both files
            bpy.data.objects.remove(o)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    tops = [o for o in bpy.data.objects if o.parent is None]
    body = bpy.data.objects.new("Body", None)
    bpy.context.scene.collection.objects.link(body)
    turn = bpy.data.objects.new("Turn", None)  # yaw, scale and ground offset; Body turns it to the facings
    bpy.context.scene.collection.objects.link(turn)
    turn.parent = body
    for o in tops:
        o.parent = turn
    turn.rotation_euler = (0, 0, math.radians(cfg["yaw"]))
    bpy.context.view_layer.update()

    pts = []
    for o in meshes:
        ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
        m = ev.to_mesh()
        pts += [o.matrix_world @ v.co for v in m.vertices]
        ev.to_mesh_clear()
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    s = cfg["length"] / (hi.y - lo.y) if "length" in cfg else cfg["height"] / (hi.z - lo.z)
    turn.scale = (s, s, s)
    centre = (lo + hi) / 2
    turn.location = (-centre.x * s, -centre.y * s, -lo.z * s)
    bpy.context.view_layer.update()
    print(f"{name}: size {((hi - lo) * s).to_tuple(1)}", flush=True)
    return body, turn, arm, meshes, (hi.z - lo.z) * s


def lowest(meshes):
    """World z of the lowest point of the posed meshes."""
    dg = bpy.context.evaluated_depsgraph_get()
    z = math.inf
    for o in meshes:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = o.matrix_world
        z = min(z, min((mw @ v.co).z for v in me.vertices))
        ev.to_mesh_clear()
    return z


def add_glow(meshes, colour, axis):
    """Emission on the pink dorsal plates (pixels where red clearly beats green). Per frame: the strength and the wave
    front (0 = tail tip .. 1 = head, along the mesh-local Y axis from axis[0] to axis[1]): plates behind it glow."""
    strength_nodes = []
    for mat in {s.material for o in meshes for s in o.material_slots if s.material}:
        nt = mat.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        if not bsdf or not bsdf.inputs["Base Color"].is_linked:
            continue
        tex = bsdf.inputs["Base Color"].links[0].from_socket
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(tex, sep.inputs[0])
        diff = nt.nodes.new("ShaderNodeMath")
        diff.operation = "SUBTRACT"
        nt.links.new(sep.outputs[0], diff.inputs[0])
        nt.links.new(sep.outputs[1], diff.inputs[1])
        mask = nt.nodes.new("ShaderNodeMapRange")
        mask.inputs["From Min"].default_value = 0.06
        mask.inputs["From Max"].default_value = 0.2
        nt.links.new(diff.outputs[0], mask.inputs["Value"])
        # Position along the body: 0 at the tail tip, 1 at the snout
        coords = nt.nodes.new("ShaderNodeTexCoord")
        sep_xyz = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(coords.outputs["Object"], sep_xyz.inputs[0])
        along = nt.nodes.new("ShaderNodeMapRange")
        along.inputs["From Min"].default_value, along.inputs["From Max"].default_value = axis
        nt.links.new(sep_xyz.outputs["Y"], along.inputs["Value"])
        # Lit behind the wave front, with a soft leading edge
        lit = nt.nodes.new("ShaderNodeMapRange")
        lit.inputs["To Min"].default_value, lit.inputs["To Max"].default_value = 1.0, 0.0
        nt.links.new(along.outputs["Result"], lit.inputs["Value"])
        both = nt.nodes.new("ShaderNodeMath")
        both.operation = "MULTIPLY"
        nt.links.new(mask.outputs["Result"], both.inputs[0])
        nt.links.new(lit.outputs["Result"], both.inputs[1])
        amount = nt.nodes.new("ShaderNodeMath")
        amount.operation = "MULTIPLY"
        nt.links.new(both.outputs[0], amount.inputs[0])
        amount.inputs[1].default_value = 0.0
        bsdf.inputs["Emission Color"].default_value = (*colour, 1)
        nt.links.new(amount.outputs[0], bsdf.inputs["Emission Strength"])
        strength_nodes.append((amount.inputs[1], lit.inputs["From Min"], lit.inputs["From Max"]))
    return strength_nodes


def add_mouth_glow(rig, colour):
    """A hot glowing core in the open mouth (charge peak and beam), riding on the head bone."""
    rig.pose("shoot", 5, 8)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.42, location=MOUTH)
    glow = bpy.context.object
    glow.name = "MouthGlow"
    mat = bpy.data.materials.new("MouthGlow")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1.0, 0.75, 0.95, 1)
    em.inputs["Strength"].default_value = 40.0
    nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    glow.data.materials.append(mat)
    glow.visible_shadow = False
    world = glow.matrix_world.copy()
    glow.parent = rig.arm
    glow.parent_type = "BONE"
    glow.parent_bone = rig.head.name
    glow.matrix_world = world
    glow.hide_render = True
    return glow


def render_cameo(name, body, rig, meshes):
    """Low three-quarter view framed on the posed model (like meshes/render_cameo.py), transparent background."""
    import numpy as np
    w, h, elev = 960, 640, math.radians(28)
    scene = bpy.context.scene
    for o in scene.objects:
        if o.type == "MESH" and o not in meshes:
            o.hide_render = True  # the shadow catcher
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.cycles.samples = 128
    render_sprites.face(body, 0, FACINGS)
    bpy.context.view_layer.update()
    rig.pose("idle", 0, 8)
    render_sprites.face(body, 6, FACINGS)
    cam = scene.camera
    cam.location = Vector((0, -50 * math.cos(elev), 50 * math.sin(elev)))
    cam.rotation_euler = (math.radians(90) - elev, 0, 0)
    bpy.context.view_layer.update()
    right = cam.matrix_world.to_3x3() @ Vector((1, 0, 0))
    up = cam.matrix_world.to_3x3() @ Vector((0, 1, 0))
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in meshes:
        me = o.evaluated_get(dg).to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        m = np.array(o.matrix_world)
        pts.append(co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3])
        o.evaluated_get(dg).to_mesh_clear()
    pts = np.concatenate(pts)
    u, v = pts @ np.array(right), pts @ np.array(up)
    cu, cv = (u.min() + u.max()) / 2, (v.min() + v.max()) / 2
    cam.data.ortho_scale = max(u.max() - u.min(), (v.max() - v.min()) * w / h) * 1.06
    loc = Vector(cam.location)
    cam.location = loc + right * cu + up * cv - (loc @ right) * right - (loc @ up) * up
    out = os.path.join(HERE, "..", "..", "..", "assets", "units", "renders", name + ".png")
    render_sprites.render_to(os.path.normpath(out))
    print("cameo", out, flush=True)


HERO = {"godz": ("shoot", 4, 8), "kong": ("roar", 0, 1)}


def render_art(name, body, rig, meshes, glow, mouth, height):
    """Banner (whole body) and portrait (head and shoulders) of the hero pose, low camera, transparent."""
    import numpy as np
    scene = bpy.context.scene
    for o in scene.objects:
        if o.type == "MESH" and o not in meshes and o is not mouth:
            o.hide_render = True  # the shadow catcher
    scene.cycles.samples = 160
    anim, step, n = HERO[name]
    render_sprites.face(body, 0, FACINGS)
    bpy.context.view_layer.update()
    info = rig.pose(anim, step, n)
    if isinstance(info["glow"], tuple):
        strength, wave, mouth_on = info["glow"]
        for amount, edge0, edge1 in glow:
            amount.default_value = strength * 1.15
            edge0.default_value, edge1.default_value = wave - 0.15, wave
    if mouth:
        mouth.hide_render = True  # reads as a white ball this close; the lit plates carry the moment
    if name == "kong":
        scene.view_settings.exposure = 1.3  # black fur: lift it for a portrait
    render_sprites.face(body, 5 if name == "godz" else 7, FACINGS)
    cam = scene.camera
    elev = math.radians(14)
    cam.location = Vector((0, -50 * math.cos(elev), 50 * math.sin(elev)))
    cam.rotation_euler = (math.radians(90) - elev, 0, 0)
    bpy.context.view_layer.update()
    right = cam.matrix_world.to_3x3() @ Vector((1, 0, 0))
    up = cam.matrix_world.to_3x3() @ Vector((0, 1, 0))
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in meshes:
        me = o.evaluated_get(dg).to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        m = np.array(o.matrix_world)
        pts.append(co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3])
        o.evaluated_get(dg).to_mesh_clear()
    pts = np.concatenate(pts)
    out_dir = os.path.normpath(os.path.join(HERE, "..", "..", "px-ui", "titans"))
    loc0 = Vector(cam.location)
    for kind, (w, h), keep, margin in (("banner", (1800, 900), None, 1.04), ("portrait", (960, 640), 0.52, 1.02)):
        sel = pts if keep is None else pts[pts[:, 2] > keep * height]
        if keep is not None and name == "godz":
            # head and shoulders: the front of the body only (the tail rises behind him)
            fwd = sel @ np.array(body.matrix_world.to_3x3() @ Vector((0, 1, 0)))
            sel = sel[fwd > np.percentile(fwd, 55)]
        u, v = sel @ np.array(right), sel @ np.array(up)
        cu, cv = (u.min() + u.max()) / 2, (v.min() + v.max()) / 2
        scene.render.resolution_x, scene.render.resolution_y = w, h
        cam.data.ortho_scale = max(u.max() - u.min(), (v.max() - v.min()) * w / h) * margin
        cam.location = loc0 + right * cu + up * cv - (loc0 @ right) * right - (loc0 @ up) * up
        render_sprites.render_to(os.path.join(out_dir, f"{name}-{kind}.png"))
        print("art", kind, flush=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    name, out = argv[0], argv[1]
    cfg = TITANS[name]
    anims = argv[2:] or list(cfg["steps"])
    only = [int(f) for f in os.environ.get("PX_TITAN_FACINGS", "").split(",") if f]

    body, turn, arm, meshes, height = import_titan(name, cfg)
    water_set = False
    os.environ.setdefault("PX_LIGHT", "hd")
    os.environ.setdefault("PX_UNIT_PX", "3.5")
    render_sprites.setup(cfg["frame"], int(os.environ.get("PX_SAMPLES", "48")))
    rig = (Godzilla if name == "godz" else Kong)(arm)
    glow = add_glow(meshes, cfg["glow"], cfg["glow_axis"]) if "glow" in cfg else []
    mouth = add_mouth_glow(rig, (1.0, 0.3, 0.8)) if name == "godz" else None
    base_loc = turn.location.copy()
    base_basis = turn.matrix_basis.copy()

    if "cameo" in anims:
        render_cameo(name, body, rig, meshes)
        return
    if "art" in anims:
        render_art(name, body, rig, meshes, glow, mouth, height)
        return

    for anim in anims:
        n = cfg["steps"][anim]
        facings_n = cfg.get("facings", FACINGS)
        facings = [DIE_FACING] if anim == "die" else (only or range(facings_n))
        frame = cfg.get("frames", {}).get(anim, cfg["frame"])
        scene = bpy.context.scene
        scene.render.resolution_x = scene.render.resolution_y = frame
        scene.camera.data.ortho_scale = frame / (float(os.environ["PX_UNIT_PX"]) * render_sprites.DENSITY)
        if anim in ("swim", "dive", "emerge") and not water_set:
            waterline({sl.material for o in meshes for sl in o.material_slots if sl.material})
            water_set = True
        steps = [int(v) for v in os.environ.get("PX_TITAN_STEPS", "").split(",") if v] or range(n)
        for step in steps:
            # Pose at facing 0: the bone moves use world axes, so the body must not be turned yet
            render_sprites.face(body, 0, FACINGS)
            turn.matrix_basis = base_basis
            bpy.context.view_layer.update()
            info = rig.pose(anim, step, n)
            strength, wave, mouth_on = info["glow"] if isinstance(info["glow"], tuple) else (info["glow"], 1.2, False)
            for amount, edge0, edge1 in glow:
                amount.default_value = strength
                edge0.default_value, edge1.default_value = wave - 0.15, wave
            if mouth:
                mouth.hide_render = not mouth_on
            # The death fall tips the whole titan over about a ground line along its side / back
            turn.rotation_euler = (0, 0, math.radians(cfg["yaw"]))
            turn.location = base_loc
            if info.get("lift"):
                turn.location = base_loc + Vector((0, 0, info["lift"] * height))
            if info.get("sink"):
                turn.location = base_loc - Vector((0, 0, info["sink"] * height))
            if info["fall"]:
                axis, deg = info["fall"]
                pivot = Vector((0, 0, 0))
                r = Matrix.Rotation(math.radians(deg), 4, axis)
                m = Matrix.Translation(pivot) @ r @ Matrix.Translation(-pivot) @ turn.matrix_basis
                turn.matrix_basis = m
                bpy.context.view_layer.update()
                # Rest on the ground once tipped over (the shadow catcher hides everything below z 0)
                turn.location.z -= lowest(meshes)
            bpy.context.view_layer.update()
            for f in facings:
                index = step if anim == "die" else f * n + step
                path = os.path.join(out, anim, f"frame-{index:03d}.png")
                if os.path.exists(path):  # resumable
                    continue
                render_sprites.face(body, f, facings_n)
                render_sprites.render_to(path)
        print(anim, "done", flush=True)


if __name__ == "__main__":
    main()
