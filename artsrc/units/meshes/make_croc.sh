#!/bin/sh
# Nile Crocodile (CROC): import the Sketchfab mesh, render its animations (render_croc.py) and pack them into
# mods/rapx/bits/hd/soldiers/croc/<anim>.png (sequences/croc.yaml). Run from the repo root.
#   sh artsrc/units/meshes/make_croc.sh [anim ...]     (default: all; PX_RENDER_ONLY=1 keeps croc.blend)
set -e
DIR=artsrc/units/meshes
OUT=$DIR/render/croc
BLENDER="nice -n 15 ${BLENDER:-blender} -b -t 4"
[ -z "$PX_RENDER_ONLY" ] && $BLENDER -P $DIR/import_sketchfab.py -- croc $DIR/croc.blend | grep -E "parts|saved"
PX_LIGHT=hd PX_UNIT_PX=7.0 $BLENDER $DIR/croc.blend -P $DIR/render_croc.py -- $OUT "$@" | grep -E "done|Error"
mkdir -p mods/rapx/bits/hd/soldiers/croc
ANIMS=${*:-idle walk swim bite die}
for anim in $ANIMS; do
	python3 artsrc/units/pack_sprites.py $OUT/$anim mods/rapx/bits/hd/soldiers/croc/$anim.png 16
done
