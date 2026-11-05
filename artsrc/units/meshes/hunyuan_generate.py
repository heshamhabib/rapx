"""
Turns concept art (assets/units/<id>.png) into textured 3D models with the tencent/Hunyuan3D-2.1
Hugging Face Space, using the local Hugging Face login (free ZeroGPU quota, ~2.5 GPU-minutes per unit).

  ~/rapx3d/venv/bin/python artsrc/units/meshes/hunyuan_generate.py <id> [<id> ...]

Writes artsrc/units/meshes/glb/<id>.glb and skips units that already have one. Stops at the first
quota error so the rest can be run later. Needs gradio_client (installed in ~/rapx3d/venv).
"""

import os
import shutil
import sys
import time

from gradio_client import Client, handle_file
from huggingface_hub import get_token

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "glb")


def generate(client, uid):
    src = os.path.join(ROOT, "assets", "units", f"{uid}.png")
    res = client.predict(image=handle_file(src), mv_image_front=None, mv_image_back=None, mv_image_left=None,
                         mv_image_right=None, steps=30, guidance_scale=5.0, seed=1234, octree_resolution=320,
                         check_box_rembg=True, num_chunks=8000, randomize_seed=False, api_name="/generation_all")
    for r in res:
        path = r.get("value") if isinstance(r, dict) else r
        if isinstance(path, str) and path.endswith("textured_mesh.glb"):
            shutil.copy(path, os.path.join(OUT, f"{uid}.glb"))
            return True
    return False


def main():
    os.makedirs(OUT, exist_ok=True)
    client = Client("tencent/Hunyuan3D-2.1", token=get_token(), verbose=False)
    for uid in sys.argv[1:]:
        if os.path.exists(os.path.join(OUT, f"{uid}.glb")):
            print("skip", uid, flush=True)
            continue
        t = time.time()
        try:
            ok = generate(client, uid)
        except Exception as e:  # quota, queue or Space errors
            print("FAILED", uid, type(e).__name__, str(e)[:300], flush=True)
            if "quota" in str(e).lower() or "exceeded" in str(e).lower():
                break
            continue
        print("done" if ok else "no-glb", uid, round(time.time() - t), "s", flush=True)


if __name__ == "__main__":
    main()
