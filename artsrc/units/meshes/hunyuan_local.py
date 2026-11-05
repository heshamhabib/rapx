"""
Generates untextured unit shapes from the concept art (assets/units/<id>.png) with Hunyuan3D-2
running locally on the Apple GPU (MPS). Texturing is done afterwards in Blender by projecting the
concept image onto the shape (project_texture.py), because Hunyuan3D-Paint needs CUDA.

Setup (once): Hunyuan3D-2 cloned in ~/rapx3d/Hunyuan3D-2 and installed (`pip install -e`) into
~/rapx3d/venv together with its requirements. The model weights (~5 GB) download on first use.

  ~/rapx3d/venv/bin/python artsrc/units/meshes/hunyuan_local.py <id> [<id> ...]

Writes artsrc/units/meshes/shape/<id>.glb (skips ids that already have one).
"""

import os
import sys
import time

import numpy as np
import torch
from PIL import Image
from scipy.ndimage import binary_dilation, label

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "shape")


def concept_path(uid):
    """Concept image for a unit id: assets/units/<id>.png, or assets/jets/<id>.png for aircraft."""
    for folder in ("units", "jets", "units/views"):  # views: e.g. e3-unarmed-front (3D soldiers)
        path = os.path.join(ROOT, "assets", folder, f"{uid}.png")
        if os.path.exists(path):
            return path
    raise FileNotFoundError(f"no concept image for {uid} in assets/units or assets/jets")


def cut_out_white(path):
    """RGBA image with the plain white backdrop (connected to the border) made transparent."""
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    lo = a.min(-1)
    labels, _ = label(lo > 232)
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    bg = np.isin(labels, border[border > 0])
    edge = binary_dilation(bg, iterations=2) & ~bg
    alpha = np.where(bg, 0.0, 1.0)
    alpha[edge] = np.clip((255 - lo[edge]) / 60, 0, 1)
    return Image.fromarray(np.dstack([a, alpha * 255]).astype(np.uint8))


def main():
    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

    os.makedirs(OUT, exist_ok=True)
    pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        "tencent/Hunyuan3D-2", subfolder="hunyuan3d-dit-v2-0", variant="fp16", device="mps", dtype=torch.float16)
    for uid in sys.argv[1:]:
        out = os.path.join(OUT, f"{uid}.glb")
        if os.path.exists(out):
            print("skip", uid, flush=True)
            continue
        t = time.time()
        image = cut_out_white(concept_path(uid))
        mesh = pipeline(image=image, num_inference_steps=50, octree_resolution=380, num_chunks=20000,
                        generator=torch.manual_seed(1234), output_type="trimesh")[0]
        mesh.export(out)
        print("done", uid, round(time.time() - t), "s", len(mesh.faces), "faces", flush=True)


if __name__ == "__main__":
    main()
