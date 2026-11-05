#!/bin/sh
# Renders the V2RL's own rocket as the flying SCUD sprite (render_v2_rocket.py), three attitudes, into
# mods/rapx/bits/hd/fx/missile-v2*.png.   sh artsrc/units/vehicles/make_v2_rocket.sh   (from the repo root)
set -e
cd "$(dirname "$0")/../../.."
OUT=artsrc/units/meshes/render/v2rocket
rm -rf $OUT
PX_LIGHT=punchy PX_NO_GROUND=1 nice -n 15 blender -b artsrc/units/meshes/v2rl.blend -P artsrc/units/vehicles/render_v2_rocket.py -- $OUT | grep -E "rocket centre|rendered"
for a in v2 v2-climb v2-dive; do
	python3 artsrc/units/pack_sprites.py $OUT/$a mods/rapx/bits/hd/fx/missile-$a.png
done
