#!/bin/sh
# Builds the ore truck model, renders all its sprites (~25 minutes) and packs them for the game.
#   sh artsrc/units/harvester/make.sh        (from the repo root)
set -e
cd "$(dirname "$0")/../../.."
BLENDER=${BLENDER:-blender}
DIR=artsrc/units/harvester

"$BLENDER" -b -P $DIR/build_harvester.py
rm -f $DIR/harvester.blend1 && rm -rf $DIR/render
# One job at a time: parallel Blender processes crash while writing the shared Metal kernel cache
"$BLENDER" -b $DIR/harvester.blend -P $DIR/render_harvester.py -- $DIR/render 48
for image in harv harvhalf harvempty hhusk hhusk2; do
	python3 artsrc/units/pack_sprites.py $DIR/render/$image mods/rapx/bits/hd/units/$image.png
done
