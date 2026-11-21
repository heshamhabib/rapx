"""
Monument City vegetation: imports the Sketchfab grass, flower and shrub packs (tools/download_sketchfab.py --vegetation)
and turns them into single plants for build_backdrop.py to scatter over the lawns.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P artsrc/maps/monument/prep_vegetation.py

Output: build/vegetation.blend (one mesh per plant, origin at the bottom centre, named veg-<kind>-<pack>-<n>, kind
grass / flower / shrub) and build/vegetation.json (sizes).

Sizes are exaggerated on purpose: at the game's zoom a real 30 cm tuft is 3 pixels and reads as noise, so tufts are
made about 1 m across and flowers about 0.6 m, like the grass in tactics games seen from this height.
"""
import glob
import json
import os
import zipfile

import bmesh
import bpy
from mathutils import Matrix, Vector

bpy.context.preferences.filepaths.save_version = 0      # no .blend1 backup copies (they filled the disk)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
BUILD = os.path.join(HERE, "build")
SRC = os.path.join(ROOT, "assets", "inbox", "vegetation")
TMP = os.path.join(BUILD, "veg")

# pack: (kind, target size in metres: the larger of width and height after scaling, skip-name parts)
PACKS = {
    "grass": ("grass", 1.1, ()),
    "grasslp": ("grass", 1.0, ()),
    "drygrass": ("grass", 1.1, ()),
    "daisy": ("flower", 0.8, ("LOD1", "LOD2")),
    "flowers": ("flower", 0.7, ()),
    "shrubm": ("shrub", 2.4, ()),
    "shrubs": ("shrub", 2.0, ()),
    "bush": ("shrub", 1.6, ()),
}


def fix_material(mat):
    """Rebuilds the material as a lit Principled BSDF with the colour texture and its alpha as a cut-out (several
    packs import as glTF 'unlit' materials, which render as solid cards here); dithered, both sides."""
    if not mat:
        return
    nt = mat.node_tree
    texs = [n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image]
    tex = next((n for n in texs if "base" in n.image.name.lower() or "diff" in n.image.name.lower() or "albedo" in n.image.name.lower()),
               texs[0] if texs else None)
    if tex:
        image = tex.image
        nt.nodes.clear()                               # (removing nodes one by one invalidates the other references)
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.inputs["Roughness"].default_value = 0.85
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        if tex.image.channels == 4 or tex.image.depth in (32, 64, 128):
            nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
        nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    mat.use_backface_culling = False
    for attr, val in (("surface_render_method", "DITHERED"), ("blend_method", "HASHED")):
        if hasattr(mat, attr):
            try:
                setattr(mat, attr, val)
            except Exception:  # noqa: BLE001
                pass


def main():
    os.makedirs(TMP, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    lib = bpy.data.collections.new("Vegetation")
    bpy.context.scene.collection.children.link(lib)
    info = {}
    for z in sorted(glob.glob(os.path.join(SRC, "*.zip"))):
        pack = os.path.basename(z).split("__")[0]
        if pack not in PACKS:
            continue
        kind, size, skip = PACKS[pack]
        out = os.path.join(TMP, pack)
        if not os.path.isdir(out):
            with zipfile.ZipFile(z) as f:
                f.extractall(out)
        gltf = (glob.glob(os.path.join(out, "**", "*.gltf"), recursive=True) + glob.glob(os.path.join(out, "**", "*.glb"), recursive=True))[0]
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=gltf)
        new = [o for o in bpy.data.objects if o not in before]
        bpy.context.view_layer.update()
        n = 0
        for o in new:
            if o.type != "MESH" or any(s in o.name for s in skip):
                continue
            me = o.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh().copy()
            me.transform(o.matrix_world)
            xs = [v.co.x for v in me.vertices]
            ys = [v.co.y for v in me.vertices]
            zs = [v.co.z for v in me.vertices]
            if not xs:
                continue
            w, d, h = max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)
            s = size / max(w, d, h, 1e-3)
            me.transform(Matrix.Scale(s, 4) @ Matrix.Translation((-(max(xs) + min(xs)) / 2, -(max(ys) + min(ys)) / 2, -min(zs))))
            name = f"veg-{kind}-{pack}-{n}"
            me.name = name
            for m in me.materials:
                fix_material(m)
            ob = bpy.data.objects.new(name, me)
            lib.objects.link(ob)
            info[name] = {"kind": kind, "w": round(w * s, 2), "d": round(d * s, 2), "h": round(h * s, 2)}
            n += 1
        for o in new:
            bpy.data.objects.remove(o, do_unlink=True)
        print(f"{pack}: {n} plants ({kind})")
    with open(os.path.join(BUILD, "vegetation.json"), "w") as f:
        json.dump(info, f, indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, "vegetation.blend"))


main()
