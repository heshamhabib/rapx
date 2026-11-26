#!/bin/sh
# Titans (rules/titans.yaml): render every pose of both giants, then pack one trimmed sheet per animation into
# mods/rapx/bits/hd/units/titans/<titan>-<anim>.png (sequences/titans.yaml). Rendering is resumable (existing frames
# are kept): delete render/<titan>/<anim>/ to redo an animation.
#   sh artsrc/units/titans/make.sh [godz|kong ...]
set -e
cd "$(dirname "$0")/../../.."
OUT=mods/rapx/bits/hd/units/titans
mkdir -p "$OUT"
for t in ${@:-godz kong}; do
	blender -b -P artsrc/units/meshes/render_titan.py -- "$t" "artsrc/units/titans/render/$t" 2>&1 | grep -E "size|done|Error|Traceback" || true
	for d in artsrc/units/titans/render/$t/*/; do
		a=$(basename "$d")
		PX_ALPHA_FLOOR=12 PX_SHEET_WIDTH=$([ "$t" = godz ] && echo 4096 || echo 2048) python3 artsrc/units/pack_trimmed.py "$OUT/$t-$a.png" "$d"
	done
done
