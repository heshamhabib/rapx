"""
Textures an untextured unit shape (shape/<id>.glb from hunyuan_local.py) with its concept image
(assets/units/<id>.png) and writes a textured glb/<id>.glb that make.sh can render (yaw 0).

1. Puts the shape in a canonical pose: long axis along Z, centred, standing on y=0 (glTF is Y-up).
2. Finds the view the concept was drawn from: tries azimuth/elevation pairs, projects the shape's
   vertices (orthographic) and compares the silhouette with the concept's cut-out (IoU).
3. Projects the concept image onto every face visible from that view. Faces on the hidden side
   take the mirrored left/right texture (vehicles are symmetric); anything still hidden (the rear,
   the underside) gets the nearest visible colour from the image.
4. Turns the model so its front faces glTF -Z (Blender +Y) and exports it.

  ~/rapx3d/venv/bin/python artsrc/units/meshes/project_texture.py <id> [--out path.glb] [--wide] [--debug]

--wide: the model is wider than it is long (flying wings), so nose-to-tail is its short axis.
--view az,el: search for the concept's camera only near this view (when the full search picks a mirrored one).
"""

import json
import math
import os
import sys

import numpy as np
import trimesh
from PIL import Image
from scipy.ndimage import binary_dilation, binary_erosion, distance_transform_edt, label

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
FIT = 160  # silhouette resolution for the view search


def concept_path(uid):
    """Concept image for a unit id: assets/units/<id>.png, or assets/jets/<id>.png for aircraft."""
    for folder in ("units", "jets"):
        path = os.path.join(ROOT, "assets", folder, f"{uid}.png")
        if os.path.exists(path):
            return path
    raise FileNotFoundError(f"no concept image for {uid} in assets/units or assets/jets")


def concept_mask(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    labels, _ = label(a.min(-1) > 232)
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    fg = ~np.isin(labels, border[border > 0])
    return a.astype(np.uint8), fg


def bbox(mask):
    ys, xs = np.nonzero(mask)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def view_axes(az, el):
    """Camera basis for a camera at azimuth az / elevation el (degrees) looking at the origin, Y up."""
    a, e = math.radians(az), math.radians(el)
    d = np.array([math.cos(e) * math.sin(a), math.sin(e), math.cos(e) * math.cos(a)])  # object -> camera
    right = np.cross([0, 1, 0], d)
    right /= np.linalg.norm(right)
    up = np.cross(d, right)
    return d, right, up


def project(points, right, up):
    return np.stack([points @ right, -(points @ up)], axis=1)  # image x right, y down


def fit_to_box(p2, box):
    """Uniform scale + offset mapping projected points onto the pixel box (x0, y0, x1, y1)."""
    lo, hi = p2.min(0), p2.max(0)
    s = min((box[2] - box[0]) / (hi[0] - lo[0]), (box[3] - box[1]) / (hi[1] - lo[1]))
    centre_src = (lo + hi) / 2
    centre_dst = np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])
    return s, centre_dst - centre_src * s


def splat(px, shape, grow=1):
    m = np.zeros(shape, bool)
    xi = np.clip(px[:, 0].astype(int), 0, shape[1] - 1)
    yi = np.clip(px[:, 1].astype(int), 0, shape[0] - 1)
    m[yi, xi] = True
    return binary_dilation(m, iterations=grow) if grow else m


def best_view(verts, target, around=None):
    """around = (az, el): search only near that view (long thin aircraft can fool the full search)."""
    box = (0, 0, target.shape[1], target.shape[0])
    best = (-1, None)
    els = range(10, 61, 5) if around is None else range(max(5, int(around[1]) - 15), int(around[1]) + 16, 5)
    azs = range(0, 360, 5) if around is None else range(int(around[0]) - 25, int(around[0]) + 26, 5)
    for el in els:
        for az in azs:
            _, right, up = view_axes(az, el)
            p2 = project(verts, right, up)
            s, off = fit_to_box(p2, box)
            m = splat(p2 * s + off, target.shape)
            iou = (m & target).sum() / (m | target).sum()
            if iou > best[0]:
                best = (iou, (az, el))
    # Refine around the best coarse view
    az0, el0 = best[1]
    for el in np.arange(el0 - 4, el0 + 4.1, 1):
        for az in np.arange(az0 - 4, az0 + 4.1, 1):
            _, right, up = view_axes(az, el)
            p2 = project(verts, right, up)
            s, off = fit_to_box(p2, box)
            m = splat(p2 * s + off, target.shape)
            iou = (m & target).sum() / (m | target).sum()
            if iou > best[0]:
                best = (iou, (float(az), float(el)))
    return best


def main():
    uid = sys.argv[1]
    debug = "--debug" in sys.argv
    mesh = trimesh.load(os.path.join(HERE, "shape", f"{uid}.glb"), force="mesh")
    # Hunyuan shapes come out at ~1M faces; ~150k is plenty for sprites and keeps Blender quick
    if len(mesh.faces) > 160000:
        mesh = mesh.simplify_quadric_decimation(face_count=150000)

    # Canonical pose: long horizontal axis along Z, centred on x/z, standing on y = 0
    # The shape may come out turned at any angle about the vertical: align its principal horizontal
    # axis (area-weighted, so dense details do not skew it) with Z
    samples, _ = trimesh.sample.sample_surface(mesh, 200_000, seed=2)
    # Use the lower half only (the chassis): wide radar arrays or long guns up top must not decide it
    low = samples[:, 1] < samples[:, 1].min() + 0.5 * np.ptp(samples[:, 1])
    samples = samples[low]
    xz = samples[:, [0, 2]] - samples[:, [0, 2]].mean(0)
    evals, evecs = np.linalg.eigh(np.cov(xz.T))
    major = evecs[:, np.argmax(evals)]  # (x, z) direction of the long axis
    if "--wide" in sys.argv:
        # Flying wings and other aircraft wider than they are long: nose-to-tail is the short axis
        major = evecs[:, np.argmin(evals)]
    angle = math.atan2(major[0], major[1])  # angle from +Z towards +X
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-angle, [0, 1, 0]))
    v = mesh.vertices
    ext = v.max(0) - v.min(0)
    print(f"{uid}: turned {math.degrees(angle):.0f} deg to the long axis, extent x {ext[0]:.2f} z {ext[2]:.2f}")
    lo, hi = v.min(0), v.max(0)
    mesh.apply_translation([-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2])
    verts = mesh.vertices

    rgb, fg = concept_mask(concept_path(uid))
    x0, y0, x1, y1 = bbox(fg)
    pad = 4
    crop = fg[y0:y1, x0:x1]
    k = FIT / max(crop.shape)
    small = np.asarray(Image.fromarray(crop).resize((max(1, round(crop.shape[1] * k)), max(1, round(crop.shape[0] * k)))))
    target = np.zeros((small.shape[0] + 2 * pad, small.shape[1] + 2 * pad), bool)
    target[pad:-pad, pad:-pad] = small
    around = None
    if "--view" in sys.argv:
        around = tuple(float(x) for x in sys.argv[sys.argv.index("--view") + 1].split(","))
    iou, (az, el) = best_view(verts, target, around)
    print(f"{uid}: best view azimuth {az:.0f} elevation {el:.0f} (silhouette IoU {iou:.2f})")

    # Exact mapping of the chosen view onto the full-resolution concept
    d, right, up = view_axes(az, el)
    p2 = project(verts, right, up)
    s, off = fit_to_box(p2, (x0, y0, x1, y1))
    H, W = fg.shape

    # Fine fit: the bounding boxes can disagree (stores, antennas, thin parts), so also try small
    # scale changes and shifts around the box fit, scored by silhouette overlap at 1/4 resolution
    q4 = 4
    fg4 = np.asarray(Image.fromarray(fg).resize((W // q4, H // q4)))
    centre = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
    best_fit = (-1.0, s, off)
    for ds in (0.9, 0.94, 0.97, 1.0, 1.03, 1.06, 1.1):
        for dx in range(-60, 61, 12):
            for dy in range(-60, 61, 12):
                s2 = s * ds
                off2 = centre + (off - centre) * ds + np.array([dx, dy])
                m = splat((p2 * s2 + off2) / q4, fg4.shape)
                score = (m & fg4).sum() / (m | fg4).sum()
                if score > best_fit[0]:
                    best_fit = (score, s2, off2)
    print(f"{uid}: fine fit IoU {best_fit[0]:.2f} (scale x{best_fit[1] / s:.2f})")
    _, s, off = best_fit
    depth = verts @ d  # larger = closer to the camera

    # Depth buffer from points sampled densely over the surface (closest point per pixel at 1/4 resolution)
    q = 4
    zb = np.full((H // q + 1, W // q + 1), -np.inf)
    surf, _ = trimesh.sample.sample_surface(mesh, 1_500_000, seed=1)
    surf = np.concatenate([surf, verts])
    pix = ((project(surf, right, up) * s + off) / q).astype(int)
    np.maximum.at(zb, (np.clip(pix[:, 1], 0, zb.shape[0] - 1), np.clip(pix[:, 0], 0, zb.shape[1] - 1)), surf @ d)
    zb = np.maximum(zb, np.pad(zb, 1, mode="edge")[2:, 1:-1])  # close pinholes
    tol = (depth.max() - depth.min()) * 0.04

    faces = mesh.faces
    fn = mesh.face_normals
    centres = verts[faces].mean(1)

    def visible(points, normals):
        pp = project(points, right, up) * s + off
        pi = (pp / q).astype(int)
        z = zb[np.clip(pi[:, 1], 0, zb.shape[0] - 1), np.clip(pi[:, 0], 0, zb.shape[1] - 1)]
        inside = (pp[:, 0] >= 0) & (pp[:, 0] < W) & (pp[:, 1] >= 0) & (pp[:, 1] < H)
        return inside & (normals @ d > 0.05) & (points @ d >= z - tol)

    mirror = np.array([-1.0, 1.0, 1.0])
    direct = visible(centres, fn)
    mirrored = ~direct & visible(centres * mirror, fn * mirror)
    hidden = ~direct & ~mirrored
    print(f"{uid}: faces direct {direct.mean():.0%}, mirrored {mirrored.mean():.0%}, hidden {hidden.mean():.0%}")

    # Texture: the concept image with the backdrop filled by the nearest vehicle colour (no white bleed)
    inner = binary_erosion(fg, iterations=2)
    _, (iy, ix) = distance_transform_edt(~inner, return_indices=True)
    tex = rgb[iy, ix]

    # Per-corner UVs: direct / mirrored projection; hidden faces sample the colour nearest to where
    # they would project, which keeps the rear and underside in the vehicle's paint
    corners = verts[faces]  # (F, 3, 3)
    pts = corners.copy()
    pts[mirrored, :, 0] *= -1
    pc = (project(pts.reshape(-1, 3), right, up) * s + off).reshape(-1, 3, 2)
    if hidden.any():
        hc = project(centres[hidden], right, up) * s + off
        hc = np.clip(hc, [0, 0], [W - 1, H - 1])
        pc[hidden] = hc[:, None, :]
    uv = np.stack([pc[..., 0] / W, 1 - pc[..., 1] / H], -1).reshape(-1, 2)

    out_mesh = trimesh.Trimesh(vertices=corners.reshape(-1, 3), faces=np.arange(len(faces) * 3).reshape(-1, 3),
                               process=False)
    material = trimesh.visual.material.PBRMaterial(baseColorTexture=Image.fromarray(tex), roughnessFactor=0.7,
                                                   metallicFactor=0.2)
    out_mesh.visual = trimesh.visual.TextureVisuals(uv=uv, material=material)

    # Front end = the end of the long axis nearer the concept camera; turn it to -Z (Blender +Y)
    front_sign = 1.0 if d[2] > 0 else -1.0
    if front_sign > 0:
        out_mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [0, 1, 0]))
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(HERE, "glb", f"{uid}.glb")
    out_mesh.export(out)
    if "--out" not in sys.argv:
        # Tells make.sh this model already faces +Y and carries the concept's own colours
        open(os.path.join(HERE, "glb", f"{uid}.projected"), "w").close()
    with open(os.path.join(HERE, "shape", f"{uid}.view.json"), "w") as f:
        json.dump(dict(azimuth=az, elevation=el, iou=float(iou)), f)
    print("saved", out)

    if debug:
        m = splat(p2 * s + off, fg.shape, grow=2)
        dbg = rgb.copy()
        dbg[m & ~fg] = [255, 0, 255]
        dbg[~m & fg] = [0, 160, 255]
        Image.fromarray(dbg).save(os.path.join(HERE, "shape", f"{uid}.fit.png"))


if __name__ == "__main__":
    main()
