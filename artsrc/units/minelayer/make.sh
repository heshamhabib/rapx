#!/bin/sh
# Builds the minelayer model, renders its 32 facings and packs them into the game sprite.
#   sh artsrc/units/minelayer/make.sh        (from the repo root, ~2 minutes)
set -e
cd "$(dirname "$0")/../../.."
BLENDER=${BLENDER:-blender}
DIR=artsrc/units/minelayer

"$BLENDER" -b -P $DIR/build_minelayer.py
rm -f $DIR/minelayer.blend1 && rm -rf $DIR/render
# PX_UNIT_PX 3.1: ~25 world px long, a little over one cell like the classic minelayer
PX_UNIT_PX=3.1 "$BLENDER" -b $DIR/minelayer.blend -P artsrc/units/render_sprites.py -- Body $DIR/render 32 160 64
python3 artsrc/units/pack_sprites.py $DIR/render mods/rapx/bits/hd/units/mnly.png
