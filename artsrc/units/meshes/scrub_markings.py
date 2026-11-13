#!/usr/bin/env python3
"""
Paints US national markings (USAF / U.S. AIR FORCE / NAVY / ARMY / MARINES lettering, star-and-bar roundels, US flags)
out of the textures of Sketchfab models that other nations fly or drive in the game. Only units the USA alone builds
keep them.

MARKINGS below lists, per model folder (glb/sketchfab/...), the boxes (texture fractions x0, y0, x1, y1) around each
marking. Inside a box only the pixels that differ from the surrounding paint (the box's border colour) are replaced,
by inpainting from the paint around them, so panel lines and weathering next to a marking stay. The first run keeps
the untouched texture as <name>.orig.<ext> and every run starts from it, so boxes can be tuned and re-run.

  ~/rapx3d/venv/bin/python artsrc/units/meshes/scrub_markings.py [folder ...]     (needs OpenCV: the rapx3d venv)

Then re-render the units (make_sketchfab.py <unit>) and their sidebar/catalogue pictures.
"""

import os
import shutil
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
GLB = os.path.join(HERE, "glb", "sketchfab")

# folder -> {texture file: [(x0, y0, x1, y1), ...]}
MARKINGS = {
    # Iran's Boeing 707 transport (E-8C model): roundels, USAF, U.S. AIR FORCE, tail codes with US flags
    "inbox2/airlift.e8c/textures": {
        "object_0_baseColor.jpeg": [(0.030, 0.340, 0.082, 0.430), (0.230, 0.400, 0.275, 0.520),
                                    (0.545, 0.398, 0.597, 0.488), (0.760, 0.305, 0.810, 0.420),
                                    (0.100, 0.835, 0.215, 0.900), (0.250, 0.830, 0.300, 0.905),
                                    (0.745, 0.850, 0.855, 0.925), (0.655, 0.835, 0.710, 0.905)],
        "object_3_baseColor.jpeg": [(0.205, 0.090, 0.330, 0.165), (0.205, 0.310, 0.330, 0.385),
                                    (0.450, 0.570, 0.710, 0.612), (0.450, 0.858, 0.710, 0.897)],
    },
    # F-14 (also Iran): NAVY + serials, four roundels
    "inbox/f-14a_tomcat_early/textures": {
        "6c352a34-82f8-40ba-89b1-af39bf66c59e_diffuse.jpeg": [
            (0.395, 0.000, 0.445, 0.150), (0.475, 0.000, 0.525, 0.150),
            (0.620, 0.385, 0.660, 0.435), (0.730, 0.385, 0.770, 0.435),
            (0.715, 0.865, 0.780, 0.910), (0.715, 0.920, 0.780, 0.965)],
    },
    # F-104 (many nations): U.S. AIR FORCE x2, USAF, five roundels, serials
    "inbox2/jet.f104__f_104_starfighter/textures": {
        "Material.001_baseColor.png": [
            (0.330, 0.285, 0.390, 0.410), (0.505, 0.285, 0.555, 0.410),
            (0.655, 0.330, 0.710, 0.405), (0.020, 0.530, 0.130, 0.600),
            (0.270, 0.650, 0.355, 0.712), (0.555, 0.570, 0.620, 0.645),
            (0.150, 0.825, 0.235, 0.945), (0.200, 0.800, 0.345, 0.965),
            (0.680, 0.080, 0.720, 0.215), (0.820, 0.115, 0.850, 0.230)],
    },
    # E-2D Shroud Hawk (all Union nations): NAVY / USS ENTERPRISE, five roundels
    "inbox2/jet.gap__e2d_hawkeye/textures": {
        "01___Default_baseColor.jpeg": [
            (0.055, 0.020, 0.185, 0.090), (0.190, 0.025, 0.310, 0.090),
            (0.055, 0.170, 0.185, 0.240), (0.190, 0.175, 0.310, 0.240),
            (0.170, 0.580, 0.290, 0.640), (0.150, 0.895, 0.270, 0.955),
            (0.050, 0.310, 0.075, 0.360)],
    },
    # Harrier (also England, Italy, India): MARINES, roundels (grey low-contrast)
    "inbox2/jet.harrier__av_8b_harrier_ii/textures": {
        "c617e66d_dds_baseColor.png": [
            ((0.310, 0.205, 0.345, 0.255), 18), ((0.365, 0.205, 0.405, 0.255), 18),
            ((0.345, 0.395, 0.385, 0.440), 18), ((0.700, 0.400, 0.810, 0.450), 18),
            ((0.725, 0.040, 0.765, 0.140), 18), ((0.850, 0.135, 0.885, 0.235), 18)],
    },
    # V-22 (also Japan): MARINES x2, roundel (low contrast)
    "inbox2/jet.v22__bell_boeing_v_22_osprey_military_helicopter/textures": {
        "02___Default_baseColor.jpeg": [
            ((0.085, 0.710, 0.140, 0.765), 16), ((0.005, 0.765, 0.125, 0.815), 16),
            ((0.355, 0.810, 0.470, 0.870), 16)],
    },
    # M16 Quad AA (all Union): circled star, U.S.A. serial, white stars
    "inbox5/m16/textures": {
        "at1base.mtl.001_baseColor.png": [
            (0.095, 0.610, 0.200, 0.715), (0.110, 0.560, 0.165, 0.610),
            (0.580, 0.435, 0.640, 0.495), (0.430, 0.720, 0.495, 0.780),
            (0.020, 0.775, 0.070, 0.850), (0.500, 0.890, 0.555, 0.950)],
        "wheell2base.mtl.001_baseColor.png": [
            (0.095, 0.610, 0.200, 0.715), (0.110, 0.560, 0.165, 0.610),
            (0.580, 0.435, 0.640, 0.495), (0.430, 0.720, 0.495, 0.780),
            (0.020, 0.775, 0.070, 0.850), (0.500, 0.890, 0.555, 0.950)],
    },
    # CH-53 "Black Hawk" (all Union): MARINES x2, roundels
    "inbox/sikorsky_ch-53e_sea_stallion/textures": {
        "chassis.1_baseColor.png": [
            ((0.625, 0.490, 0.940, 0.560), 20), ((0.690, 0.430, 0.800, 0.490), 20),
            ((0.060, 0.760, 0.380, 0.830), 20), ((0.170, 0.690, 0.300, 0.770), 20)],
    },
    # Chinook (all Union): U.S. ARMY x3, star roundels (dark olive)
    "inbox/boeing_ch-47_chinook_military_transport_aircraft/textures": {
        name: [(0.190, 0.030, 0.300, 0.060), (0.190, 0.190, 0.300, 0.225), (0.215, 0.280, 0.245, 0.390),
               (0.395, 0.300, 0.440, 0.370), (0.105, 0.500, 0.160, 0.540), (0.455, 0.585, 0.505, 0.625),
               (0.150, 0.315, 0.180, 0.360)]
        for name in ("13___Default_baseColor.png", "Material__14524_baseColor.png")
    },
    # C-141 (Union airlift): USAF x2, roundels, U.S. AIR FORCE x2, badges, US flags, AFRC / MARCH tail bands
    "inbox2/airlift.c141/textures": {
        "C141B.1_baseColor.png": [((0.085, 0.140, 0.140, 0.200), 14), ((0.750, 0.720, 0.910, 0.810), 14)],
        "C141B.3_baseColor.png": [((0.140, 0.700, 0.200, 0.760), 14), ((0.690, 0.150, 0.870, 0.240), 14)],
        "C141B.6_baseColor.png": [((0.380, 0.040, 0.640, 0.080), 14), ((0.365, 0.080, 0.455, 0.140), 14),
                                  ((0.420, 0.440, 0.660, 0.480), 14), ((0.545, 0.475, 0.625, 0.540), 14),
                                  ((0.380, 0.280, 0.448, 0.330), 14), ((0.560, 0.680, 0.630, 0.725), 14)],
        "C141B.5_baseColor.png": [((0.590, 0.095, 0.660, 0.170), 14), ((0.560, 0.135, 0.630, 0.165), 14),
                                  ((0.490, 0.175, 0.760, 0.200), 14), ((0.520, 0.210, 0.590, 0.240), 14),
                                  ((0.185, 0.435, 0.250, 0.475), 14), ((0.210, 0.480, 0.270, 0.505), 14),
                                  ((0.080, 0.515, 0.360, 0.545), 14), ((0.255, 0.550, 0.315, 0.585), 14)],
    },
    # B-52 (Egypt airlift): roundels
    "inbox2/airlift.b52t/textures": {
        "B52.002_baseColor.png": [((0.500, 0.795, 0.570, 0.840), 14), ((0.495, 0.895, 0.575, 0.960), 14)],
    },
    # F-4 (nine nations): roundels, FC tail code, USAF caption (left/right textures are mirror images)
    "inbox2/jet.f4__mcdonnell_douglas_f_4_phantom_ii/textures": {
        "F4_P_L_baseColor.jpeg": [(0.65, 0.13, 0.7, 0.19), (0.67, 0.3, 0.705, 0.385), (0.65, 0.53, 0.7, 0.57), (0.65, 0.65, 0.7, 0.695), (0.84, 0.23, 0.945, 0.33), (0.04, 0.87, 0.41, 0.915)],
        "F4_P_R_baseColor.jpeg": [(0.3, 0.13, 0.35, 0.19), (0.295, 0.3, 0.33, 0.385), (0.3, 0.53, 0.35, 0.57), (0.3, 0.65, 0.35, 0.695), (0.055, 0.23, 0.16, 0.33), (0.59, 0.87, 0.96, 0.915)],
    },
    # F-16 (eight nations): US flag flashes and AF serials on the tail
    "inbox2/jet.f16__general_dynamics_f_16d_block_60/textures": {
        "tail.0_baseColor.png": [(0.740, 0.515, 0.995, 0.560), (0.000, 0.860, 0.260, 0.905),
                                 ((0.220, 0.440, 0.400, 0.510), 18), ((0.590, 0.900, 0.770, 0.975), 18)],
        "body.1_baseColor.png": [((0.120, 0.090, 0.240, 0.175), 14), ((0.680, 0.770, 0.780, 0.850), 14)],
        "body.3_baseColor.png": [((0.590, 0.330, 0.675, 0.460), 14), ((0.820, 0.330, 0.905, 0.460), 14)],
    },
}

THRESHOLD = 34  # colour distance from the paint that counts as marking


def scrub(path, boxes):
    root, ext = os.path.splitext(path)
    orig = f"{root}.orig{ext}"
    if not os.path.exists(orig):
        shutil.copy2(path, orig)
    img = cv2.imread(orig, cv2.IMREAD_UNCHANGED)
    alpha = img[..., 3] if img.ndim == 3 and img.shape[2] == 4 else None
    bgr = np.ascontiguousarray(img[..., :3]) if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    h, w = bgr.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    boxes = [bx if isinstance(bx[0], tuple) else (bx, THRESHOLD) for bx in boxes]
    for (x0, y0, x1, y1), thr in boxes:
        a, b, c, d = int(x0 * w), int(y0 * h), int(np.ceil(x1 * w)), int(np.ceil(y1 * h))
        region = bgr[b:d, a:c].astype(np.int32)
        border = np.concatenate([region[0], region[-1], region[:, 0], region[:, -1]])
        paint = np.median(border, axis=0)
        dist = np.sqrt(((region - paint) ** 2).sum(-1))
        mask[b:d, a:c] |= (dist > thr).astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=1)
    # keep the dilation inside the boxes
    inside = np.zeros_like(mask)
    for (x0, y0, x1, y1), _ in boxes:
        inside[int(y0 * h):int(np.ceil(y1 * h)), int(x0 * w):int(np.ceil(x1 * w))] = 255
    mask &= inside
    out = cv2.inpaint(bgr, mask, 9, cv2.INPAINT_TELEA)
    if alpha is not None:
        out = np.dstack([out, alpha])
    params = [cv2.IMWRITE_JPEG_QUALITY, 95] if ext.lower() in (".jpg", ".jpeg") else []
    cv2.imwrite(path, out, params)
    return int((mask > 0).sum())


def main():
    only = sys.argv[1:]
    for folder, textures in MARKINGS.items():
        if only and not any(o in folder for o in only):
            continue
        for name, boxes in textures.items():
            n = scrub(os.path.join(GLB, folder, name), boxes)
            print(f"{folder}/{name}: {len(boxes)} markings, {n} pixels repainted")


if __name__ == "__main__":
    main()
