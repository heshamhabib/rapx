"""
Imports a downloaded Sketchfab model (glTF, settings in sketchfab_models.py) as a unit .blend for the sprite
renderers (run by make_sketchfab.py):

  tank     "Hull" + "Turret" roots          -> artsrc/units/tanks/render_tank.py (hull 0-31, turret 32-63)
  vehicle  "Body" root                       -> artsrc/units/render_sprites.py
  rocket   "Body" root with a "Rocket" child -> artsrc/units/vehicles/render_vehicle.py v2rl
  air      "Body" root                       -> artsrc/units/render_sprites.py (no ground shadow)
  heli     "Body" root + "Rotor" roots       -> render_sprites.py + render_rotor.py

The model is turned nose to +Y, scaled to its length, centred on the origin with the ground (lowest point)
at z=0. Unlike AI models (import_glb.py + split_turret.py), Sketchfab models come in parts, so turrets,
rockets and rotors are picked by part; a tank's merged parts are cut by height around the turret ring.

Team colour (PlayerColorShift, rules/palettes.yaml: hue 0.22-0.45 becomes the owner's colour) is added in
the materials: the "team" areas turn green with the texture's light and dirt kept, every other green is
moved to olive (hue 0.13) so camouflage and glass do not take the team colour. Like the other HD units,
only part of each unit is in team colour: a whole unit in team colour reads as a flat block.

  Blender -b -P artsrc/units/meshes/import_sketchfab.py -- <unit id> <out.blend>

Prints the offsets for rules/*.yaml (Turreted Offset, muzzle LocalOffset, rotor overlay Offsets).
"""

import colorsys
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sketchfab_models import MODELS  # noqa: E402

# World distance per Blender unit in game. Ground units: 1024/24 wdist per px x UNIT_PX 3.5 x 1.4 (sequence
# scale) x 0.88 (the 50 degree camera shortens screen-vertical ground distances; 0.88 splits the difference),
# as split_turret.py. Aircraft: UNIT_PX 9.1 at the jets' 1/3 scale. Heights show at cos(50) on screen.
WDIST_GROUND = 1024 / 24 * 3.5 * 1.4 * 0.88
WDIST_AIR = 1024 / 24 * 9.1 * 0.88
HEIGHT = math.cos(math.radians(50)) / 0.88

argv = sys.argv[sys.argv.index("--") + 1:]
UNIT, OUT = argv[0], argv[1]
CFG = MODELS[UNIT]
KIND = CFG["kind"]
WDIST = WDIST_AIR if KIND in ("air", "heli") else WDIST_GROUND

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(HERE, "glb", "sketchfab", CFG["src"]))
bpy.context.view_layer.update()
for o in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
    mw = o.matrix_world.copy()
    if o.data.users > 1:
        o.data = o.data.copy()
    o.data.transform(mw)
    o.parent = None
    o.matrix_world = Matrix.Identity(4)
    o.data.transform(Matrix.Rotation(math.radians(CFG.get("yaw", 0)), 4, "Z"))
for o in list(bpy.context.scene.objects):
    if o.type != "MESH" or o.name in CFG.get("drop", ()) or any(
            m and m.name.split(".")[0] in CFG.get("drop_materials", ()) for m in o.data.materials) or any(
            part in o.name for part in CFG.get("drop_contains", ())):
        bpy.data.objects.remove(o)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if "attach" in CFG:
    # A second model mounted on this one (the Tesla Tank: the RA2 Tesla coil on a T-62 hull), in model units
    # after the yaw: its base centred on "at" (x, y, z), scaled to "height". Tanks use it as the turret.
    a = CFG["attach"]
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(HERE, "glb", "sketchfab", a["src"]))
    bpy.context.view_layer.update()
    new = [o for o in bpy.context.scene.objects if o not in before]
    parts = [o for o in new if o.type == "MESH"]
    for o in parts:
        mw = o.matrix_world.copy()
        if o.data.users > 1:
            o.data = o.data.copy()
        o.data.transform(mw)
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
    for o in [o for o in new if o.type != "MESH"]:
        bpy.data.objects.remove(o)
    pts = np.concatenate([np.array([v.co[:] for v in o.data.vertices]) for o in parts])
    alo, ahi = pts.min(axis=0), pts.max(axis=0)
    k = a["height"] / (ahi[2] - alo[2])
    move = Matrix.Translation(Vector(a["at"])) @ Matrix.Scale(k, 4) @ Matrix.Translation(
        -Vector(((alo[0] + ahi[0]) / 2, (alo[1] + ahi[1]) / 2, alo[2])))
    for o in parts:
        o.data.transform(move)
    if a.get("plate"):
        # A steel turret plate under it (radius, thickness): covers the ring the replaced turret leaves open
        r, th = a["plate"]
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=r, radius2=r * 0.94, depth=th)
        bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((a["at"][0], a["at"][1], a["at"][2] + th / 2)))
        me = bpy.data.meshes.new("TurretPlate")
        bm.to_mesh(me)
        bm.free()
        steel = bpy.data.materials.new("TurretPlate")
        steel.use_nodes = True
        bsdf = steel.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (0.09, 0.09, 0.085, 1)
        bsdf.inputs["Metallic"].default_value = 0.6
        bsdf.inputs["Roughness"].default_value = 0.55
        me.materials.append(steel)
        plate = bpy.data.objects.new("TurretPlate", me)
        bpy.context.scene.collection.objects.link(plate)
        parts.append(plate)
        # the attached model stands on the plate
        for o in parts[:-1]:
            o.data.transform(Matrix.Translation(Vector((0, 0, th))))
    for o in parts:
        o["px_attach"] = True
    meshes += parts
if "keep_near" in CFG:
    # The file holds more than the unit (the MiG-21 comes as a formation with smoke trails): keep the parts
    # whose centre is within r of (x, y), model units after the yaw
    (kx, ky), kr = CFG["keep_near"]
    for o in list(meshes):
        c = sum((v.co for v in o.data.vertices), Vector()) / max(len(o.data.vertices), 1)
        if (Vector((c.x, c.y)) - Vector((kx, ky))).length > kr:
            bpy.data.objects.remove(o)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if CFG.get("snap"):
    # Models posed at an angle: turn the long axis of the plan view exactly onto Y (the yaw got it within ~45);
    # snap "wing" for planes whose wingspan is longer than the fuselage
    pts = np.concatenate([np.array([v.co[:2] for v in o.data.vertices]) for o in meshes])
    pts -= pts.mean(axis=0)
    w, vecs = np.linalg.eigh(np.cov(pts.T))
    ax = vecs[:, np.argmax(w)]
    if CFG["snap"] == "wing":  # wingspan longer than the fuselage: the long axis is the wing, the nose is across it
        ax = np.array([-ax[1], ax[0]])
    if ax[1] < 0:
        ax = -ax
    turn = math.atan2(ax[0], ax[1])  # counter-clockwise turn that brings the axis onto +Y
    for o in meshes:
        o.data.transform(Matrix.Rotation(turn, 4, "Z"))
    print(f"snapped {math.degrees(turn):.1f} degrees")
if CFG.get("fix_normals"):
    # SketchUp-style exports with flipped faces render as a light/dark triangle patchwork: point every face
    # outwards and drop the custom normals
    for o in meshes:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(o.data)
        bm.free()
        if o.data.has_custom_normals:
            o.data.free_normals_split() if hasattr(o.data, "free_normals_split") else None
            if "custom_normal" in o.data.attributes:
                o.data.attributes.remove(o.data.attributes["custom_normal"])
if "waterline" in CFG:
    # Ships: cut everything below the waterline (model units), so the lowest point (the render's ground) is the
    # water surface
    wz = CFG["waterline"]
    for o in list(meshes):
        bm = bmesh.new()
        bm.from_mesh(o.data)
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, wz), plane_no=(0, 0, 1), clear_inner=True)
        bm.to_mesh(o.data)
        bm.free()
        if not o.data.polygons:
            bpy.data.objects.remove(o)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
for o in meshes:  # skinned parts (C-17 gear) would otherwise move back to their rest pose
    for m in [m for m in o.modifiers if m.type == "ARMATURE"]:
        o.modifiers.remove(m)
rotor_names = {n for r in CFG.get("rotors", []) for n in r}

if CFG.get("scrub_red"):
    # Paints red markings (emblems, insignia) to the texture's average body colour
    for img in {n.image for m in bpy.data.materials if m.node_tree for n in m.node_tree.nodes
                if n.type == "TEX_IMAGE" and n.image}:
        px = np.empty(len(img.pixels), dtype=np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(-1, 4)
        r, g, b = px[:, 0], px[:, 1], px[:, 2]
        red = (r > 1.6 * g) & (r > 1.6 * b) & (r > 0.12)
        if red.any():
            body = px[~red, :3].mean(axis=0)
            px[red, :3] = body * (0.85 + 0.3 * (r[red] / max(r[red].max(), 1e-6)))[:, None]
            img.pixels.foreach_set(px.ravel())
            img.pack()
            print(f"scrubbed {int(red.sum())} red pixels in {img.name}")

if CFG.get("scrub_white"):
    # Paints white markings (another nation's crosses, numbers) to the texture's average body colour
    for img in {n.image for m in bpy.data.materials if m.node_tree for n in m.node_tree.nodes
                if n.type == "TEX_IMAGE" and n.image}:
        px = np.empty(len(img.pixels), dtype=np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(-1, 4)
        rgb = px[:, :3]
        white = (rgb.min(axis=1) > 0.45) & (rgb.max(axis=1) - rgb.min(axis=1) < 0.12)
        if white.any():
            px[white, :3] = rgb[~white].mean(axis=0)
            img.pixels.foreach_set(px.ravel())
            img.pack()
            print(f"scrubbed {int(white.sum())} white pixels in {img.name}")


def bounds(objs):
    pts = np.concatenate([np.array([v.co[:] for v in o.data.vertices]) for o in objs if len(o.data.vertices)])
    return pts.min(axis=0), pts.max(axis=0)


# Scale and centre: the span (or the bounds without rotor discs) sets the length; the ground is the lowest point
lo, hi = bounds([o for o in meshes if o.name not in rotor_names] or meshes)
y0, y1 = CFG.get("span", (lo[1], hi[1]))
scale = CFG["length"] / (y1 - y0)
centre = Vector(((lo[0] + hi[0]) / 2 if "span" not in CFG else 0.0, (y0 + y1) / 2, lo[2]))
to_unit = Matrix.Scale(scale, 4) @ Matrix.Translation(-centre)
for o in meshes:
    o.data.transform(to_unit)
lo, hi = bounds(meshes)


def model_point(p):
    """A model-unit point (after the yaw) in scaled unit coordinates."""
    return Vector(((p[0] - centre.x) * scale, (p[1] - centre.y) * scale, (p[2] - centre.z) * scale if len(p) > 2 else 0))


def cut(obj, keep, name_suffix):
    """Splits obj: faces passing keep(centre) move to a new object (returned, None if there are none)."""
    top = obj.copy()
    top.data = obj.data.copy()
    top.name = obj.name + name_suffix
    bpy.context.scene.collection.objects.link(top)
    for o, keep_top in ((obj, False), (top, True)):
        bm = bmesh.new()
        bm.from_mesh(o.data)
        drop = [f for f in bm.faces if keep(f.calc_center_median()) != keep_top]
        bmesh.ops.delete(bm, geom=drop, context="FACES")
        bm.to_mesh(o.data)
        bm.free()
    if not top.data.polygons:
        bpy.data.objects.remove(top)
        return None
    return top


def root(name, parts, offset=Vector()):
    r = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(r)
    for o in parts:
        if offset.length:
            o.data.transform(Matrix.Translation(-offset))
        o.parent = r
    return r


offsets = []
if KIND == "tank":
    t = CFG["tank"]
    pivot = model_point(t["pivot"])
    rx, ry = (r * scale for r in t["ring"])
    turret_parts = [o for o in meshes if o.name in t["turret"]]
    attached = [o for o in meshes if o.get("px_attach")]

    with_gun = "cut" in t  # merged parts: the gun in front of the turret goes with it too

    def in_turret(c, z_cut):
        if c.z <= z_cut:
            return False
        dx, dy = (c.x - pivot.x) / rx, (c.y - pivot.y) / ry
        gun = with_gun and c.y > pivot.y and abs(c.x - pivot.x) < rx * 0.6
        return dx * dx + dy * dy <= 1 or gun

    cuts = {n: z for n, z in t.get("mixed", {}).items()}
    if "cut" in t:
        cuts.update({o.name: t["cut"] for o in meshes if o not in turret_parts and not o.get("px_attach")})
    for name, z in cuts.items():
        z_cut = (z - centre.z) * scale
        part = cut(bpy.data.objects[name], lambda c, z_cut=z_cut: in_turret(c, z_cut), ".turret")
        if part:
            turret_parts.append(part)
    if t.get("replace_turret"):
        # The model's own turret goes; the attached model is the turret
        for o in turret_parts:
            bpy.data.objects.remove(o)
        turret_parts = attached
    hull_parts = [o for o in bpy.context.scene.objects if o.type == "MESH" and o not in turret_parts]
    root("Hull", hull_parts)
    turret = root("Turret", turret_parts, Vector((pivot.x, pivot.y, 0)))  # turns about the actor centre
    turret["px_pivot"] = (pivot.x, pivot.y, 0.0)
    offsets.append(f"Turreted Offset: {round(pivot.y * WDIST)},{round(-pivot.x * WDIST)},0")
    gun = [bpy.data.objects[t["muzzle"]]] if "muzzle" in t else turret_parts
    # the muzzle is the gun's front tip, or the top of a turret that fires upwards (the Tesla coil's ball)
    tip = max((v.co for o in gun for v in o.data.vertices), key=lambda c: c.z if t.get("muzzle_top") else c.y)
    offsets.append(f"muzzle LocalOffset: {round(tip.y * WDIST)},{round(-tip.x * WDIST)},{round(tip.z * WDIST * HEIGHT)}")
elif KIND == "rocket":
    rocket_parts = [o for o in meshes if o.name in CFG["rocket"]]
    for name, z in CFG.get("rocket_above", {}).items():
        # Loose pieces of a shared part whose centre is above z (model units) are the rocket
        z_cut = (z - centre.z) * scale
        obj = bpy.data.objects[name]
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        high, seen = set(), set()
        for f in bm.faces:
            if f.index in seen:
                continue
            island, stack = [], [f]
            seen.add(f.index)
            while stack:
                g = stack.pop()
                island.append(g.index)
                for e in g.edges:
                    for h in e.link_faces:
                        if h.index not in seen:
                            seen.add(h.index)
                            stack.append(h)
            zs = [v.co.z for i in island for v in bm.faces[i].verts]
            if sum(zs) / len(zs) > z_cut:
                high.update(island)
        bm.free()
        rocket = obj.copy()
        rocket.data = obj.data.copy()
        rocket.name = obj.name + ".rocket"
        bpy.context.scene.collection.objects.link(rocket)
        for o, keep in ((obj, False), (rocket, True)):
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if (f.index in high) != keep], context="FACES")
            bm.to_mesh(o.data)
            bm.free()
        rocket_parts.append(rocket)
        print(f"rocket pieces from {name}: {len(high)} faces")
    body = root("Body", [o for o in meshes if o not in rocket_parts])
    rocket = root("Rocket", rocket_parts)
    rocket.parent = body
else:
    rotor_parts = []
    for i, names in enumerate(CFG.get("rotors", [])):
        parts = [bpy.data.objects[n] for n in names]
        rlo, rhi = bounds(parts)
        # The blades' centroid is the hub (a three-blade rotor's bounding box is off-centre)
        pts = np.concatenate([np.array([v.co[:] for v in o.data.vertices]) for o in parts])
        hub = Vector((pts[:, 0].mean(), pts[:, 1].mean(), rlo[2]))
        root(f"Rotor{i}", parts, hub)["px_hub"] = tuple(hub)
        rotor_parts += parts
        offsets.append(f"rotor {i} Offset: {round(hub.y * WDIST)},{round(-hub.x * WDIST)},{round(hub.z * WDIST * HEIGHT)}"
                       f"  (disc radius {max(rhi[0] - rlo[0], rhi[1] - rlo[1]) / 2:.2f})")
    root("Body", [o for o in meshes if o not in rotor_parts])


# --- Weapon stations (IDEA-34, artsrc/jets/loadout_table.py) ------------------------------------------------
sys.path.insert(0, os.path.join(HERE, "..", "..", "jets"))
from loadout_table import LOADOUTS  # noqa: E402

if UNIT in LOADOUTS:
    import json

    import ordnance
    import storefind

    lo_cfg = LOADOUTS[UNIT]
    body = bpy.data.objects["Body"]
    bpy.context.view_layer.update()
    found, _ = storefind.find([o for o in body.children if o.type == "MESH"])
    to_units = CFG["length"] / lo_cfg["real_length"]  # Blender units per metre
    depsgraph = bpy.context.evaluated_depsgraph_get()
    stations = []

    def split_all(picked):
        """Builds every store object from the untouched meshes, then removes all picked faces at once."""
        out = {name: split_faces(picks, name, delete=False) for name, picks in picked.items()}
        per_object = {}
        for picks in picked.values():
            for obj_name, faces in picks.items():
                per_object.setdefault(obj_name, set()).update(faces)
        for obj_name, faces in per_object.items():
            src = bpy.data.objects[obj_name]
            bm = bmesh.new()
            bm.from_mesh(src.data)
            bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index in faces], context="FACES")
            bm.to_mesh(src.data)
            bm.free()
        return out

    def split_faces(picks, name, delete=True):
        """Moves the picked faces ({object name: [face indices]}) into one new object."""
        bm_out = bmesh.new()
        uv_out = bm_out.loops.layers.uv.new("UVMap")
        mats = []
        for obj_name, faces in picks.items():
            src = bpy.data.objects[obj_name]
            bm = bmesh.new()
            bm.from_mesh(src.data)
            bm.faces.ensure_lookup_table()
            uv_src = bm.loops.layers.uv.active
            wanted = set(faces)
            vmap = {}
            for f in bm.faces:
                if f.index not in wanted:
                    continue
                mat = src.data.materials[f.material_index] if src.data.materials else None
                if mat not in mats:
                    mats.append(mat)
                vs = []
                for v in f.verts:
                    if v.index not in vmap:
                        vmap[v.index] = bm_out.verts.new(v.co)
                    vs.append(vmap[v.index])
                try:
                    nf = bm_out.faces.new(vs)
                except ValueError:
                    continue
                nf.material_index = mats.index(mat)
                nf.smooth = f.smooth
                if uv_src:  # keep the texture mapping
                    for l, nl in zip(f.loops, nf.loops):
                        nl[uv_out].uv = l[uv_src].uv
            if delete:
                bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index in wanted], context="FACES")
                bm.to_mesh(src.data)
            bm.free()
        mesh = bpy.data.meshes.new(name)
        bm_out.to_mesh(mesh)
        bm_out.free()
        for m in mats:
            mesh.materials.append(m)
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        return obj

    def leading_edge(x):
        """Front edge of the wing (or airframe) at span position x: the first hit scanning down from the nose."""
        y = CFG["length"] / 2
        while y > -CFG["length"] / 2:
            hit, *_ = bpy.context.scene.ray_cast(depsgraph, Vector((x, y, 50.0)), Vector((0, 0, -1)))
            if hit:
                return y
            y -= 0.02
        return 0.0

    def underside(x, y):
        """Height of the airframe's underside at (x, y): a ray cast up from below."""
        hit, loc, *_ = bpy.context.scene.ray_cast(depsgraph, Vector((x, y, -50.0)), Vector((0, 0, 1)))
        return loc.z if hit else None

    picked = {}  # store name -> {object name: [face indices]}, all chosen before any faces are cut out
    for i, st in enumerate(lo_cfg["stations"]):
        if "model" not in st:
            continue
        for side in (["C"] if st.get("centre") else ["R", "L"]):
            x, y, z, rx, ry, rz = st["model"]
            x *= -1 if side == "L" else 1
            for f in found:
                c = f["centre"]
                if abs(c[0] - x) <= rx and abs(c[1] - y) <= ry and abs(c[2] - z) <= rz:
                    for obj_name, faces in f["faces"]:
                        picked.setdefault(f"Store{i}{side}", {}).setdefault(obj_name, []).extend(faces)
    split = split_all(picked)

    for i, st in enumerate(lo_cfg["stations"]):
        sides = ["C"] if st.get("centre") else ["R", "L"]
        entry = {"weapon": st["weapon"], "shots": st.get("shots", 1), "stores": []}
        if st.get("internal"):  # weapons bay: fires from under the fuselage, nothing to show or hide
            entry["internal"] = True
            stations.append(entry)
            continue
        for side in sides:
            mirror = -1 if side == "L" else 1
            name = f"Store{i}{side}"
            if "model" in st:
                obj = split.get(name)
                if obj is None:
                    print(f"WARNING {UNIT} station {i}{side}: no model store found there")
                    continue
            else:
                x, y = st["at"]
                x *= mirror
                obj = ordnance.build(st["add"], to_units, name)
                if y == "lead":  # hung forward on its pylon like the real thing: the front half shows from above
                    y = leading_edge(x) - 0.08 * obj["px_length"]
                z = underside(x, y)
                r = obj["px_radius"]
                z = (z - r * 1.25) if z is not None else 0.2
                ordnance.mount(obj, (x, y, z))
            obj.parent = body
            obj["px_store"] = f"{i}{side}"
            pts = np.array([v.co[:] for v in obj.data.vertices])
            front = pts[pts[:, 1] >= np.percentile(pts[:, 1], 90)].mean(0)  # the nose: where the shot leaves
            entry["stores"].append({"side": side, "name": name, "nose": [float(v) for v in front]})
        stations.append(entry)
        print(f"station {i} {st['weapon']}: {[s['side'] for s in entry['stores']]}")
    json.dump({"unit": UNIT, "stations": stations, "wdist_per_unit": WDIST, "height_factor": HEIGHT},
              open(os.path.splitext(OUT)[0] + ".stores.json", "w"), indent=1)


# --- Team colour -----------------------------------------------------------------------------------------
team = CFG.get("team", {})
team_boxes = team.get("boxes") or ([team["box"]] if "box" in team else [])  # "boxes": several areas
if team_boxes:
    # Per-vertex mask read by the materials: 1 inside a box (fractions of the bounds, unit coordinates)
    boxes = [([lo[i] + (hi[i] - lo[i]) * b[2 * i] for i in range(3)],
              [lo[i] + (hi[i] - lo[i]) * b[2 * i + 1] for i in range(3)]) for b in team_boxes]
    for o in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
        if o.parent and o.parent.get("px_hub"):  # rotor blades never take the team colour
            o.data.attributes.new("px_team", "FLOAT", "POINT")
            continue
        shift = (o.parent.get("px_pivot") or o.parent.get("px_hub") or (0, 0, 0)) if o.parent else (0, 0, 0)
        attr = o.data.attributes.new("px_team", "FLOAT", "POINT")
        co = np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3) + np.array(shift)
        inside = np.any([np.all((co >= b_lo) & (co <= b_hi), axis=1) for b_lo, b_hi in boxes], axis=0)
        inside = inside.astype(np.float32)
        # box_materials: only those materials (name prefixes) take the box, e.g. a stripe on the paint, not the glass
        if team.get("box_materials") and not any(m and m.name.split(".")[0] in team["box_materials"]
                                                 for m in o.data.materials):
            inside[:] = 0
        attr.data.foreach_set("value", inside)


def colour_source(nt, bsdf):
    """The socket feeding Base Color, made into a node output if it was a plain value."""
    base = bsdf.inputs["Base Color"]
    if base.is_linked:
        return base.links[0].from_socket
    rgb = nt.nodes.new("ShaderNodeRGB")
    rgb.outputs[0].default_value = base.default_value
    return rgb.outputs[0]


def math_node(nt, op, a, b=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def combine_hsv(nt, h, s, v):
    n = nt.nodes.new("ShaderNodeCombineColor")
    n.mode = "HSV"
    for i, x in enumerate((h, s, v)):
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = x
        else:
            nt.links.new(x, n.inputs[i])
    return n.outputs[0]


def mix(nt, fac, a, b):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    socket = {s.identifier: s for s in n.inputs}
    nt.links.new(fac, socket["Factor_Float"])
    nt.links.new(a, socket["A_Color"])
    nt.links.new(b, socket["B_Color"])
    return next(s for s in n.outputs if s.identifier == "Result_Color")


def team_shader(mat, team_material):
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf:
        return
    src = colour_source(nt, bsdf)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    sep.mode = "HSV"
    nt.links.new(src, sep.inputs[0])
    h, s, v = sep.outputs
    green = math_node(nt, "MULTIPLY", math_node(nt, "GREATER_THAN", h, 0.2), math_node(nt, "LESS_THAN", h, 0.47))
    green = math_node(nt, "MULTIPLY", green, math_node(nt, "GREATER_THAN", s, 0.06))
    out = mix(nt, green, src, combine_hsv(nt, 0.13, s, v))  # other greens -> olive
    if CFG.get("darken"):  # darker paint than the model's own (the AX-47's gunmetal concept vs a white X-47B)
        dark = nt.nodes.new("ShaderNodeMixRGB")
        dark.blend_type = "MULTIPLY"
        dark.inputs[0].default_value = 1.0
        nt.links.new(out, dark.inputs[1])
        dark.inputs[2].default_value = (CFG["darken"],) * 3 + (1,)
        out = dark.outputs[0]
        for name, value in (("Metallic", 0.25), ("Roughness", 0.55)):  # matte paint: chrome reads as silver
            for link in list(bsdf.inputs[name].links):
                nt.links.remove(link)
            bsdf.inputs[name].default_value = value
    if CFG.get("paint"):
        # National paint (IDEA-17 shared launcher chassis): the paint's hue and saturation over the model's own
        # light and shade (Color blend), then brightened or darkened by paint_value
        r, g, b = (c ** 2.2 for c in CFG["paint"])  # given in display values
        paint_value = CFG.get("paint_value", (max(CFG["paint"]) / MODEL_VALUE) ** 2.2)
        tint = nt.nodes.new("ShaderNodeMixRGB")
        tint.blend_type = "COLOR"
        tint.inputs[0].default_value = CFG.get("paint_strength", 0.85)
        nt.links.new(out, tint.inputs[1])
        tint.inputs[2].default_value = (r, g, b, 1)
        out = tint.outputs[0]
        if paint_value != 1.0:
            bright = nt.nodes.new("ShaderNodeMixRGB")
            bright.blend_type = "MULTIPLY"
            bright.inputs[0].default_value = 1.0
            nt.links.new(out, bright.inputs[1])
            bright.inputs[2].default_value = (min(paint_value, 60.0),) * 3 + (1,)
            out = bright.outputs[0]
        # Matte paint: shiny (metallic) models mirror the grey sky and look white under the HD light
        bsdf.inputs["Specular IOR Level"].default_value = 0.3
        for name, value in (("Metallic", 0.15), ("Roughness", 0.62)):
            for link in list(bsdf.inputs[name].links):
                nt.links.remove(link)
            bsdf.inputs[name].default_value = value

    mask = None
    if team_material:
        mask = math_node(nt, "ADD", 1.0, 0.0)
    if team_boxes:
        attr = nt.nodes.new("ShaderNodeAttribute")
        attr.attribute_type = "GEOMETRY"
        attr.attribute_name = "px_team"
        mask = attr.outputs["Fac"] if mask is None else math_node(nt, "MAXIMUM", mask, attr.outputs["Fac"])
    if team.get("greens"):
        mask = green if mask is None else math_node(nt, "MAXIMUM", mask, green)
    if mask is not None:
        # Shader colours are linear: brightness tests and the team green are worked out in display (sRGB-ish)
        # values, so dark paint is not mistaken for black and the green reads at ~50% saturation on screen.
        v_display = math_node(nt, "POWER", v, 1 / 2.2)
        lit = nt.nodes.new("ShaderNodeMapRange")  # near-black (rubber, texture shadows) stays as it is
        lit.interpolation_type = "SMOOTHSTEP"
        lit.inputs["From Min"].default_value, lit.inputs["From Max"].default_value = 0.08, 0.2
        nt.links.new(v_display, lit.inputs["Value"])
        fac = math_node(nt, "MULTIPLY", mask, lit.outputs["Result"])
        team_v = math_node(nt, "MULTIPLY_ADD", v_display, 1.15, clamp=True)
        team_v.node.inputs[2].default_value = 0.06
        team_v = math_node(nt, "POWER", math_node(nt, "MINIMUM", team_v, 0.85), 2.2)
        team_s = math_node(nt, "MULTIPLY_ADD", s, 0.2, clamp=True)
        team_s.node.inputs[2].default_value = 0.7
        out = mix(nt, fac, out, combine_hsv(nt, 1 / 3, team_s, team_v))
    nt.links.new(out, bsdf.inputs["Base Color"])


# Legacy texture pass (3tnk, kept so its sprites do not change): olive paint -> team green etc.
def rgb_to_hsv(rgb):
    mx, mn = rgb.max(axis=1), rgb.min(axis=1)
    d = mx - mn
    h = np.zeros_like(mx)
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    nz = d > 1e-6
    rm, gm = nz & (mx == r), nz & (mx == g) & (mx != r)
    bm_ = nz & ~rm & ~gm
    h[rm] = ((g - b)[rm] / d[rm]) % 6
    h[gm] = (b - r)[gm] / d[gm] + 2
    h[bm_] = (r - g)[bm_] / d[bm_] + 4
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0)
    return h / 6, s, mx


def hsv_to_rgb(h, s, v):
    i = np.floor(h * 6).astype(int) % 6
    f = h * 6 - np.floor(h * 6)
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    out = np.choose(i, [v, q, p, p, t, v]), np.choose(i, [t, v, v, q, p, p]), np.choose(i, [p, p, t, v, v, q])
    return np.stack(out, axis=1)


def recolour(image, mode, markings):
    px = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    h, s, v = rgb_to_hsv(px[:, :3])
    if markings:
        white = (s < 0.15) & (v > 0.45)
        h, s, v = np.where(white, 0.2, h), np.where(white, 0.12, s), np.where(white, 0.2, v)
    paint = (h > 0.11) & (h < 0.34) & (s > 0.03) & (v > 0.06)
    if mode == "team":
        # Team green, lighter than the dark olive so dark team colours (blue) do not turn black
        h = np.where(paint, 1 / 3, h)
        s = np.where(paint, np.clip(0.3 + s * 1.4, 0, 0.55), s)
        v = np.where(paint, np.clip(v * 1.5 + 0.04, 0, 0.8), v)
    elif mode == "paint":
        # Olive drab well below the team-colour hue range (the bluish rim light shifts lit edges towards it),
        # a little lighter to read on the HD terrain
        h = np.where(paint, 0.13, h)
        s = np.where(paint, np.clip(s * 1.3, 0, 0.35), s)
        v = np.where(paint, np.clip(v * 1.25, 0, 1), v)
    else:
        mask = (h > 0.2) & (h < 0.47)
        s = np.where(mask, 0, s)
    px[:, :3] = hsv_to_rgb(h, s, v)
    image.pixels.foreach_set(px.ravel())
    image.pack()


def legacy_paint(mat, done):
    lp = CFG["legacy_paint"]
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf:
        return
    mode = "team" if mat.name in lp["team"] else "paint" if mat.name in lp["paint"] else "other"
    paint = mode != "other"
    # Matte paint like the real thing
    bsdf.inputs["Roughness"].default_value = 0.72 if paint else 0.6
    bsdf.inputs["Metallic"].default_value = 0.1 if paint else 0.3
    for link in list(bsdf.inputs["Roughness"].links) + list(bsdf.inputs["Metallic"].links):
        mat.node_tree.links.remove(link)
    base = bsdf.inputs["Base Color"]
    if base.is_linked:
        image = base.links[0].from_node.image
        if image.name not in done:
            recolour(image, mode, mat.name in lp.get("markings", ()))
            done.add(image.name)
    else:
        r, g, b, a = base.default_value
        hh, ss, vv = colorsys.rgb_to_hsv(r, g, b)
        if mode == "team" and 0.11 < hh < 0.34:
            base.default_value = (*colorsys.hsv_to_rgb(1 / 3, min(0.3 + ss * 1.4, 0.55), min(vv * 1.5, 1)), a)
        elif mode == "paint" and 0.11 < hh < 0.34:
            base.default_value = (*colorsys.hsv_to_rgb(0.13, min(ss * 1.3, 0.35), min(vv * 1.25, 1)), a)
        elif 0.2 < hh < 0.47:
            base.default_value = (vv, vv, vv, a)


def cockpit_glass(mat):
    """Glass parts (named glass, canopy or window) render as flat white from above: make them dark, glossy
    canopy glass that reflects the sky."""
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if mat.node_tree else None
    if not bsdf:
        return False
    trans = bsdf.inputs.get("Transmission Weight")
    # By name only: other see-through materials (a propeller's blur disc) must stay see-through
    if not any(w in mat.name.lower() for w in ("glass", "canopy", "window")):
        return False
    for name in ("Base Color", "Alpha", "Roughness", "Metallic") + (("Transmission Weight",) if trans else ()):
        for link in list(bsdf.inputs[name].links):
            mat.node_tree.links.remove(link)
    bsdf.inputs["Base Color"].default_value = (0.02, 0.025, 0.03, 1)
    bsdf.inputs["Alpha"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.08
    bsdf.inputs["Metallic"].default_value = 0.0
    if trans:
        trans.default_value = 0.0
    return True


def base_value(mat):
    """Display brightness (max channel) of a material's own base colour: its texture's mean, or its colour."""
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if mat.node_tree else None
    if not bsdf:
        return None
    base = bsdf.inputs["Base Color"]
    if base.is_linked:
        tex = next((n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image), None)
        if tex is None:
            return None
        px = np.empty(len(tex.image.pixels), dtype=np.float32)
        tex.image.pixels.foreach_get(px)
        rgb = px.reshape(-1, 4)[:, :3].mean(axis=0)  # image pixels are linear in Blender
        return float(rgb.max()) ** (1 / 2.2)
    return float(max(base.default_value[:3])) ** (1 / 2.2)


# The model's average paint brightness (area-weighted), so national paint (CFG paint) keeps its own brightness
MODEL_VALUE = 0.5
if CFG.get("paint") and "paint_value" not in CFG:
    total = weighted = 0.0
    values = {}
    for o in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
        if not o.material_slots:
            continue
        idx = np.empty(len(o.data.polygons), dtype=np.int32)
        area = np.empty(len(o.data.polygons), dtype=np.float32)
        o.data.polygons.foreach_get("material_index", idx)
        o.data.polygons.foreach_get("area", area)
        for i, slot in enumerate(o.material_slots):
            if not slot.material:
                continue
            if slot.material.name not in values:
                values[slot.material.name] = base_value(slot.material)
            v = values[slot.material.name]
            if v is not None:
                a = float(area[idx == i].sum())
                total += a
                weighted += a * v
    MODEL_VALUE = max(0.05, weighted / total) if total else 0.5
    print("model paint value", round(MODEL_VALUE, 3))

done = set()
for mat in {s.material for o in bpy.context.scene.objects if o.type == "MESH" for s in o.material_slots if s.material}:
    mat["px_finish"] = True  # render_sprites.py PX_LIGHT=punchy leaves the model's own finish alone
    if "legacy_paint" not in CFG and cockpit_glass(mat):
        continue
    if "legacy_paint" in CFG:
        legacy_paint(mat, done)
    else:
        team_shader(mat, mat.name in team.get("materials", ()))

for line in offsets:
    print(line)
print("parts", len([o for o in bpy.context.scene.objects if o.type == "MESH"]), "scale", round(scale, 4),
      "size", tuple(round(float(hi[i] - lo[i]), 2) for i in range(3)))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("saved", OUT)
