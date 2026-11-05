#!/bin/sh
# Textures, renders and previews AI jet shapes (shape/<file>.glb from hunyuan_local.py), then updates the
# jet sequences. Preview: render/<file>/frame-00 (should face north) and frame-08 (west) side by side in
# artsrc/units/meshes/preview-jets.png, to check each nose direction (fix with FIX= in make.sh).
#   sh artsrc/units/meshes/process_jets.sh <file> [<file> ...]
set -e
cd "$(dirname "$0")/../../.."
DIR=artsrc/units/meshes
for id in "$@"; do
	FLAGS=""
	case $id in
		ab-2-wraith|ax-47-stingray) FLAGS="--wide" ;;
		tv-160-swanwing) FLAGS="--view 225,35" ;;
	esac
	~/rapx3d/venv/bin/python $DIR/project_texture.py $id $FLAGS --debug | grep -E "view|fit"
	sh $DIR/make.sh $id | grep -E "^packed"
done
python3 - "$@" <<'PY'
import sys
from PIL import Image, ImageDraw
ids = sys.argv[1:]
tile = 200
out = Image.new("RGBA", (tile * 2 * min(4, len(ids)), tile * ((len(ids) + 3) // 4)), (110, 130, 90, 255))
d = ImageDraw.Draw(out)
for k, uid in enumerate(ids):
    x, y = (k % 4) * tile * 2, (k // 4) * tile
    for j, f in enumerate((0, 8)):
        im = Image.open(f"artsrc/units/meshes/render/{uid}/frame-{f:02d}.png").convert("RGBA")
        im.thumbnail((tile, tile))
        out.alpha_composite(im, (x + j * tile + (tile - im.width) // 2, y + (tile - im.height) // 2))
    d.text((x + 4, y + 4), uid, fill=(255, 255, 255, 255))
out.save("artsrc/units/meshes/preview-jets.png")
PY
python3 artsrc/jets/make_jets.py
