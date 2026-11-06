"""
Procedural aircraft weapons for IDEA-34 (real jet loadouts): missiles, bombs and rocket pods built in Blender at their
real proportions, for jets whose models came without their weapons. Imported by
artsrc/units/meshes/import_sketchfab.py.

  build(kind, metres_to_units) -> Blender object, nose along +Y, centred on the origin

Kinds (real length m, diameter m, fins, paint):
"""

import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

# Real models (Sketchfab, CC-BY; tools/download_sketchfab.py --missiles, unzipped into
# artsrc/units/meshes/glb/sketchfab/missiles/<kind>/): used instead of the procedural shape for both the fired sprite
# (render_missiles.py) and the stores hung on jets (import_sketchfab.py "add"). kind: real length in metres.
# The long axis is turned onto +Y with the nose forward (the pointed end: the one with less width at its tip).
MISSILE_MODELS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "units", "meshes",
                                               "glb", "sketchfab", "missiles"))
REAL = {
    "aim9": 2.87,      # AIM-9 Sidewinder (rickslash)
    "aim120": 3.66,    # AIM-120C AMRAAM (Jeyhun1985)
    "aim54": 3.96,     # AIM-54 Phoenix (MustafaGarip)
    "r73": 2.9,        # R-73 (jokesforboats)
    "r77": 3.6,        # R-77 (MustafaGarip)
    "r27t": 3.7,       # R-27T (KojfDiscord, War Thunder)
    "agm65": 2.49,     # AGM-65B Maverick (xFORTUNAx)
    "kh29": 3.9,       # Kh-29T (xFORTUNAx)
    "gbu": 3.27,       # GBU-12 Paveway II (KojfDiscord, War Thunder)
    "s8": 1.57,        # S-8KOM 80 mm rocket (xFORTUNAx)
    "tomahawk": 5.56,  # BGM-109 Tomahawk (rickslash)
}
# Models whose tail tip is narrower than the nose (a jet nozzle behind the fins): nose detection reversed
NOSE_FLIP = {"tomahawk"}

# kind: (length, diameter, nose fraction, fin span (x diameter), canards, body colour (linear), band colour)
KINDS = {
    "aim9": (3.0, 0.127, 0.10, 4.4, True, (0.82, 0.82, 0.8), (0.95, 0.75, 0.1)),      # short-range air-to-air
    "r73": (2.9, 0.17, 0.10, 3.4, True, (0.78, 0.79, 0.76), (0.6, 0.15, 0.1)),
    "aim120": (3.66, 0.178, 0.12, 2.8, False, (0.85, 0.85, 0.83), (0.95, 0.75, 0.1)),  # medium-range air-to-air
    "r77": (3.6, 0.2, 0.12, 2.4, False, (0.74, 0.76, 0.72), (0.6, 0.15, 0.1)),
    "aim54": (4.0, 0.38, 0.14, 2.4, False, (0.88, 0.88, 0.86), (0.95, 0.75, 0.1)),    # long-range Phoenix
    "agm65": (2.5, 0.3, 0.12, 2.4, False, (0.2, 0.22, 0.18), (0.95, 0.75, 0.1)),       # Maverick
    "mk82": (2.2, 0.27, 0.22, 1.6, False, (0.07, 0.08, 0.055), (0.95, 0.75, 0.1)),    # unguided bomb
    "gbu": (3.3, 0.36, 0.18, 1.5, True, (0.09, 0.1, 0.075), (0.95, 0.75, 0.1)),     # laser-guided bomb
    "hydra": (1.06, 0.07, 0.15, 3.2, False, (0.75, 0.76, 0.72), (0.95, 0.75, 0.1)),  # pod rocket in flight
    "pod": (2.0, 0.42, 0.0, 0.0, False, (0.25, 0.26, 0.23), (0.1, 0.1, 0.1)),        # rocket pod
    # National rocket launchers (IDEA-17), the rocket each one fires
    "gmlrs_us": (3.94, 0.227, 0.12, 1.9, True, (0.45, 0.38, 0.24), (0.95, 0.75, 0.1)),   # GMLRS, HIMAX (sand)
    "gmlrs_uk": (3.94, 0.227, 0.12, 1.9, True, (0.12, 0.15, 0.08), (0.9, 0.9, 0.85)),    # Hailstorm (green)
    "gmlrs_fr": (3.94, 0.227, 0.12, 1.9, True, (0.15, 0.17, 0.13), (0.1, 0.2, 0.6)),     # LRX
    "gmlrs_de": (3.94, 0.227, 0.12, 1.9, True, (0.08, 0.12, 0.07), (0.6, 0.12, 0.08)),   # MARZ II
    "gmlrs_it": (3.94, 0.227, 0.12, 1.9, True, (0.25, 0.24, 0.16), (0.1, 0.4, 0.15)),    # Saetta
    "trg300": (4.9, 0.30, 0.13, 2.0, False, (0.8, 0.8, 0.78), (0.6, 0.05, 0.05)),        # Kasirga 300 mm
    "fatah": (7.0, 0.40, 0.15, 1.8, True, (0.35, 0.33, 0.2), (0.05, 0.3, 0.1)),           # Fatah guided rocket
    "type12": (5.0, 0.35, 0.14, 2.0, False, (0.85, 0.86, 0.85), (0.15, 0.15, 0.16)),     # Type 12 anti-ship missile
    "k239": (4.0, 0.239, 0.12, 2.0, True, (0.2, 0.24, 0.18), (0.95, 0.75, 0.1)),         # Chunmoo 239 mm
    "tos220": (3.3, 0.22, 0.28, 1.6, False, (0.4, 0.32, 0.18), (0.55, 0.06, 0.04)),      # TOS-1A thermobaric
    "vilkha": (7.6, 0.30, 0.13, 1.8, True, (0.1, 0.16, 0.08), (0.8, 0.7, 0.1)),          # Vilkha 300 mm
    "grad122": (2.87, 0.122, 0.13, 2.4, False, (0.16, 0.18, 0.1), (0.6, 0.08, 0.05)),    # 9M22 Grad
    "pinaka": (4.9, 0.214, 0.12, 2.2, False, (0.14, 0.16, 0.09), (0.85, 0.4, 0.05)),     # Pinaka 214 mm
    "sakr": (3.0, 0.122, 0.13, 2.4, False, (0.5, 0.42, 0.28), (0.1, 0.35, 0.12)),        # Sakr 122 mm cluster
    "phl16": (7.2, 0.37, 0.13, 1.7, True, (0.55, 0.56, 0.55), (0.6, 0.05, 0.05)),        # PHL-16 370 mm
    "fajr5": (6.5, 0.333, 0.13, 1.8, False, (0.12, 0.14, 0.12), (0.6, 0.05, 0.05)),      # Fajr-5 333 mm
    "shard136": (3.5, 0.32, 0.12, 0.0, False, (0.2, 0.21, 0.22), (0.6, 0.05, 0.05)),      # Shard-136 delta-wing drone
}

# Delta-wing drones (Shahed-style): wing span in metres; the wing fills the rear half, with fins on the tips
DELTA = {"shard136": 2.5}

# Kinds with mid-body wings (cruise / anti-ship missiles): wing span as a multiple of the fin span
MIDWINGS = {"type12": 1.5}


def material(name, colour, rough=0.45, metal=0.1):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*colour, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    m["px_finish"] = True
    return m


def body_of_revolution(bm, profile, segments=20, mat_index=None):
    """profile: [(y, radius)] from tail to nose; a closed lathe shape around the Y axis."""
    rings = []
    for y, r in profile:
        if r <= 1e-6:
            rings.append([bm.verts.new((0, y, 0))])
            continue
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / segments), y,
                                    r * math.sin(2 * math.pi * i / segments))) for i in range(segments)])
    faces = []
    for a, b in zip(rings, rings[1:]):
        if len(a) == 1 or len(b) == 1:
            ring, tip = (b, a[0]) if len(a) == 1 else (a, b[0])
            for i in range(segments):
                faces.append(bm.faces.new((ring[i], ring[(i + 1) % segments], tip)))
        else:
            for i in range(segments):
                faces.append(bm.faces.new((a[i], a[(i + 1) % segments], b[(i + 1) % segments], b[i])))
    if len(rings[0]) > 1:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
    if mat_index is not None:
        for f in faces:
            f.material_index = mat_index
    return faces


def fin(bm, y0, y1, root, span, angle, thick, mat_index):
    """A swept fin from the body (radius root) outwards, at angle (radians) around Y."""
    c, s = math.cos(angle), math.sin(angle)
    tip_len = (y1 - y0) * 0.45
    pts = [(root, y0), (root, y1), (root + span, y0 + tip_len * 0.4), (root + span, y0)]
    verts = []
    for side in (-thick / 2, thick / 2):
        for r, y in pts:
            x, z = r * c - side * s, r * s + side * c
            verts.append(bm.verts.new((x, y, z)))
    a, b = verts[:4], verts[4:]
    faces = [bm.faces.new(a), bm.faces.new(list(reversed(b)))]
    for i in range(4):
        faces.append(bm.faces.new((a[i], a[(i + 1) % 4], b[(i + 1) % 4], b[i])))
    for f in faces:
        f.material_index = mat_index


def delta_wing(bm, L, R, span, mat_index):
    """A flat delta wing under the rear half of the body, with an upright fin on each tip."""
    y_tail = -L / 2
    t = 0.012 * L
    half = span / 2
    for side in (-1, 1):
        # root leading edge, root trailing edge, tip trailing edge, tip leading edge
        pts = [(0, 0.1 * L), (0, y_tail + 0.02 * L), (side * half, y_tail + 0.04 * L), (side * half, y_tail + 0.2 * L)]
        bottom = [bm.verts.new((x, y, -t / 2)) for x, y in pts]
        top = [bm.verts.new((x, y, t / 2)) for x, y in pts]
        faces = [bm.faces.new(bottom), bm.faces.new(list(reversed(top)))]
        for i in range(4):
            faces.append(bm.faces.new((bottom[i], bottom[(i + 1) % 4], top[(i + 1) % 4], top[i])))
        for f in faces:
            f.material_index = mat_index
        # wingtip fin, standing up
        fx = side * half
        fin_pts = [(y_tail + 0.04 * L, 0), (y_tail + 0.2 * L, 0), (y_tail + 0.08 * L, 0.18 * L), (y_tail + 0.02 * L, 0.18 * L)]
        a = [bm.verts.new((fx - t / 2, y, z)) for y, z in fin_pts]
        b = [bm.verts.new((fx + t / 2, y, z)) for y, z in fin_pts]
        faces = [bm.faces.new(a), bm.faces.new(list(reversed(b)))]
        for i in range(4):
            faces.append(bm.faces.new((a[i], a[(i + 1) % 4], b[(i + 1) % 4], b[i])))
        for f in faces:
            f.material_index = mat_index


def real_model(kind, scale, name=None):
    """Imports the real model of kind as one mesh: nose along +Y, centred, real length x scale."""
    folder = os.path.join(MISSILE_MODELS, kind)
    path = next(os.path.join(folder, f) for f in sorted(os.listdir(folder)) if f.endswith((".gltf", ".glb")))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    bpy.context.view_layer.update()

    # One mesh in world coordinates
    mesh = bpy.data.meshes.new(name or f"ord-{kind}")
    bm = bmesh.new()
    for o in meshes:
        tmp = o.data.copy()
        tmp.transform(o.matrix_world)
        offset = len(mesh.materials)
        for m in o.data.materials:
            mesh.materials.append(m)
        bm2 = bmesh.new()
        bm2.from_mesh(tmp)
        for f in bm2.faces:
            f.material_index += offset
        tmp2 = bpy.data.meshes.new("tmp")
        bm2.to_mesh(tmp2)
        bm2.free()
        bm.from_mesh(tmp2)
        bpy.data.meshes.remove(tmp2)
        bpy.data.meshes.remove(tmp)
    bm.to_mesh(mesh)
    bm.free()
    for o in new:
        bpy.data.objects.remove(o)

    pts = np.array([v.co[:] for v in mesh.vertices])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    axis = int(np.argmax(hi - lo))
    centre = (lo + hi) / 2
    pts -= centre
    # Nose: the end whose last 3% is narrower (a point or seeker, not the fins and nozzle)
    length = hi[axis] - lo[axis]
    others = [i for i in range(3) if i != axis]
    radius = np.linalg.norm(pts[:, others], axis=1)
    tip_hi = radius[pts[:, axis] > length * 0.47]
    tip_lo = radius[pts[:, axis] < -length * 0.47]
    nose_sign = 1 if (tip_hi.max(initial=0) <= tip_lo.max(initial=0)) else -1
    if kind in NOSE_FLIP:
        nose_sign = -nose_sign
    # Rotate so that axis * nose_sign becomes +Y
    fwd = Vector([0, 0, 0])
    fwd[axis] = nose_sign
    rot = fwd.rotation_difference(Vector((0, 1, 0))).to_matrix().to_4x4()
    k = (REAL[kind] * scale) / length
    mesh.transform(Matrix.Scale(k, 4) @ rot @ Matrix.Translation(Vector(-centre)))
    for p in mesh.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new(name or f"ord-{kind}", mesh)
    bpy.context.scene.collection.objects.link(obj)
    body = np.percentile(radius, 40) * k  # typical body radius, not the fin span
    obj["px_radius"] = float(body)
    obj["px_length"] = float(REAL[kind] * scale)
    return obj


def build(kind, scale, name=None):
    if kind in REAL and os.path.isdir(os.path.join(MISSILE_MODELS, kind)):
        return real_model(kind, scale, name)
    length, diam, nose, fin_span, canards, colour, band = KINDS[kind]
    L, R = length * scale, diam * scale / 2
    bm = bmesh.new()
    mats = [material(f"ord-{kind}", colour), material("ord-dark", (0.06, 0.065, 0.07), 0.3, 0.2),
            material(f"ord-band-{kind}", band, 0.5)]
    y_tail, y_nose = -L / 2, L / 2
    if kind == "pod":
        prof = [(y_tail, R * 0.85), (y_tail + 0.08 * L, R), (y_nose - 0.12 * L, R), (y_nose, R * 0.75)]
        body_of_revolution(bm, prof, mat_index=0)
        # Rocket tubes in the front face
        for k in range(7):
            a = 2 * math.pi * k / 6
            cx, cz = (0, 0) if k == 6 else (R * 0.45 * math.cos(a), R * 0.45 * math.sin(a))
            tube = [(y_nose - 0.02 * L, R * 0.16), (y_nose + 0.005 * L, R * 0.16)]
            fs = body_of_revolution(bm, tube, segments=10, mat_index=1)
            for v in {v for f in fs for v in f.verts}:
                v.co.x += cx
                v.co.z += cz
    else:
        n = nose * L
        tail = 0.04 * L
        prof = [(y_tail, R * 0.7), (y_tail + tail, R), (y_nose - n, R)]
        for t in (0.35, 0.65, 0.88, 1.0):  # ogive nose
            prof.append((y_nose - n + n * t, R * math.sqrt(max(0.0, 1 - t ** 1.6))))
        body_of_revolution(bm, prof, mat_index=0)
        # Seeker / nose cap and the warhead band
        cap = [(y_nose - n * 0.35, R * 0.86), (y_nose - n * 0.12, R * 0.5), (y_nose, 0)]
        body_of_revolution(bm, cap, mat_index=1)
        band_y = y_nose - n - 0.08 * L
        body_of_revolution(bm, [(band_y - 0.025 * L, R * 1.012), (band_y + 0.025 * L, R * 1.012)], mat_index=2)
        span = R * fin_span
        if kind in DELTA:
            delta_wing(bm, L, R, DELTA[kind] * scale, 0)
        for k in range(4 if fin_span > 0 else 0):
            fin(bm, y_tail + tail, y_tail + tail + 0.14 * L, R, span, math.pi / 4 + k * math.pi / 2, 0.015 * L, 0)
            if canards:
                fin(bm, y_nose - n - 0.1 * L, y_nose - n - 0.02 * L, R, span * 0.55,
                    math.pi / 4 + k * math.pi / 2, 0.012 * L, 0)
            elif kind in MIDWINGS:
                fin(bm, -0.12 * L, 0.1 * L, R, span * MIDWINGS[kind], math.pi / 4 + k * math.pi / 2, 0.012 * L, 0)
            elif kind in ("aim120", "r77", "aim54", "agm65"):
                fin(bm, -0.05 * L, 0.12 * L, R, span * 0.6, math.pi / 4 + k * math.pi / 2, 0.012 * L, 0)
    mesh = bpy.data.meshes.new(name or f"ord-{kind}")
    bm.to_mesh(mesh)
    bm.free()
    for m in mats:
        mesh.materials.append(m)
    for p in mesh.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new(name or f"ord-{kind}", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj["px_radius"] = R
    obj["px_length"] = L
    return obj


def mount(obj, at):
    obj.data.transform(Matrix.Translation(Vector(at)))
