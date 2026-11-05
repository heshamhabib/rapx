"""
Colours a soldier mesh (in Blender) from its concept views: the front concept assets/units/<id>.png and the
ChatGPT back / left-side views assets/units/views/<id>-back.png, <id>-left.png (the right side is the left view
mirrored). Each vertex takes a blend of the views facing it (weighted by how squarely the surface faces each
camera), written to a "Col" colour attribute. Works on the rest pose, so it can be run on the Mixamo-rigged
mesh too.

Conventions (Blender): the soldier stands on z=0, faces -Y; his left side is +X.
"""

import os

import bpy
import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def load_view(path):
    """(rgb float array, figure bbox x0,y0,x1,y1) with the white backdrop ignored."""
    im = bpy.data.images.load(path, check_existing=True)
    im.colorspace_settings.name = "Non-Color"  # keep the file's sRGB values; converted to linear in paint()
    w, h = im.size
    px = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(px)
    a = px.reshape(h, w, 4)[::-1, :, :3].copy()  # Blender stores rows bottom-up
    fig = a.min(-1) < 0.93
    ys, xs = np.nonzero(fig)
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    # Grow the figure's colours over the backdrop, so samples just outside its edge (hands, boots, the
    # rifle tip) pick up the soldier, not white
    a = a.copy()
    known = fig.copy()
    for _ in range(24):
        grown = known.copy()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(known, (dy, dx), axis=(0, 1))
            take = src & ~grown
            a[take] = np.roll(a, (dy, dx), axis=(0, 1))[take]
            grown |= take
        known = grown
    return a, box, fig


def views(uid):
    """[(image, bbox, figure mask, camera direction (towards the camera), horizontal axis in world)]."""
    out = []
    front = os.path.join(ROOT, "assets", "units", f"{uid}.png")
    back = os.path.join(ROOT, "assets", "units", "views", f"{uid}-back.png")
    left = os.path.join(ROOT, "assets", "units", "views", f"{uid}-left.png")
    # Empty-handed views (the weapon is a separate prop) win when they exist
    unarmed = os.path.join(ROOT, "assets", "units", "views", f"{uid}-unarmed-%s.png")
    if os.path.exists(unarmed % "front"):
        front, back, left = unarmed % "front", unarmed % "back", unarmed % "left"
    # camera at -Y looking +Y: image right = +X
    out.append((*load_view(front), np.array([0, -1, 0.0]), np.array([1, 0, 0.0])))
    if os.path.exists(back):
        # camera at +Y looking -Y: image right = -X
        out.append((*load_view(back), np.array([0, 1, 0.0]), np.array([-1, 0, 0.0])))
    if os.path.exists(left):
        img, box, fig = load_view(left)
        # camera at +X looking -X: image right = +Y
        out.append((img, box, fig, np.array([1, 0, 0.0]), np.array([0, 1, 0.0])))
        # right side: the left view mirrored, camera at -X looking +X: image right = -Y
        w = img.shape[1]
        out.append((img[:, ::-1], (w - box[2], box[1], w - box[0], box[3]), fig[:, ::-1], np.array([-1, 0, 0.0]), np.array([0, -1, 0.0])))
    return out


def paint(obj, uid, sharpness=3.0):
    me = obj.data
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(n, 3) @ np.array(obj.matrix_world)[:3, :3].T + np.array(obj.matrix_world)[:3, 3]
    nor = np.empty(n * 3)
    me.vertices.foreach_get("normal", nor)
    nor = nor.reshape(n, 3)
    zmin, zmax = co[:, 2].min(), co[:, 2].max()

    acc = np.zeros((n, 3))
    wsum = np.zeros(n)
    for img, (x0, y0, x1, y1), fig, cam, right in views(uid):
        h, w = img.shape[:2]
        # Vertical: the figure's top and bottom are the mesh's; horizontal uses the same pixels-per-metre,
        # centred on the figure (the views may be slightly narrower or wider than the mesh)
        ppm = (y1 - y0) / (zmax - zmin)
        horiz = co @ right
        hc = (horiz.max() + horiz.min()) / 2
        px = (x0 + x1) / 2 + (horiz - hc) * ppm
        py = y0 + (zmax - co[:, 2]) * ppm
        xi = np.clip(px.astype(int), 0, w - 1)
        yi = np.clip(py.astype(int), 0, h - 1)
        facing = np.clip(nor @ cam, 0, 1) ** sharpness + 1e-4
        # A view only counts where the point lands on the soldier in that image (not the backdrop)
        facing = facing * np.where(fig[yi, xi], 1.0, 0.002)
        acc += img[yi, xi] * facing[:, None]
        wsum += facing
    col = acc / wsum[:, None]
    # Studio highlights on thin parts (fingertips, buckles) come out near-white; cap the brightness of
    # greyish colours. Saturated colours (the team-colour green) stay untouched.
    lum = col @ np.array([0.299, 0.587, 0.114])
    grey = (col.max(1) - col.min(1)) < 0.25
    cap = 0.5
    over = grey & (lum > cap)
    col[over] *= (cap / lum[over])[:, None]

    attr = me.color_attributes.get("Col") or me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    rgba = np.concatenate([col ** 2.2, np.ones((n, 1))], axis=1)  # sRGB image -> linear
    attr.data.foreach_set("color", rgba.astype(np.float32).ravel())
    me.color_attributes.active_color = attr
    return attr


def vertex_color_material(name="SoldierPaint"):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    bsdf.inputs["Roughness"].default_value = 0.7
    # The views already carry their studio lighting; darken and saturate so the scene lights don't wash
    # the uniform out (team-colour green stays the most saturated colour)
    hsv = nt.nodes.new("ShaderNodeHueSaturation")
    hsv.inputs["Saturation"].default_value = 1.4
    hsv.inputs["Value"].default_value = 1.2
    nt.links.new(attr.outputs["Color"], hsv.inputs["Color"])
    # Warm tint against the bluish sky light, which otherwise turns the olive uniform grey
    warm = nt.nodes.new("ShaderNodeMix")
    warm.data_type = "RGBA"
    warm.blend_type = "MULTIPLY"
    warm.inputs["Factor"].default_value = 1.0
    warm.inputs[7].default_value = (1.0, 0.94, 0.74, 1)  # B input of the colour mix
    nt.links.new(hsv.outputs["Color"], warm.inputs[6])
    # Contrast on the uniform, and ambient occlusion darkening the creases (vest, pouches, limbs)
    bc = nt.nodes.new("ShaderNodeBrightContrast")
    bc.inputs["Contrast"].default_value = 0.12
    nt.links.new(warm.outputs[2], bc.inputs["Color"])
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = 0.12
    nt.links.new(bc.outputs["Color"], ao.inputs["Color"])
    nt.links.new(ao.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Specular IOR Level"].default_value = 0.35
    bsdf.inputs["Roughness"].default_value = 0.6
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat
