#!/bin/sh
# Renders the V2RL's own rocket as the flying SCUD sprite (render_v2_rocket.py), three attitudes, into
# mods/rapx/bits/hd/fx/missile-v2*.png.   sh artsrc/units/vehicles/make_v2_rocket.sh   (from the repo root)
# Other launchers: sh artsrc/units/vehicles/make_v2_rocket.sh zolf one   (the Zolfaghar: one missile of its pair)
#                 sh artsrc/units/vehicles/make_v2_rocket.sh mlrs first  (the Thunderhead MLRS: one of its rockets)
set -e
cd "$(dirname "$0")/../../.."
UNIT=${1:-v2rl}
NAME=v2; [ "$UNIT" != v2rl ] && NAME=$UNIT
OUT=artsrc/units/meshes/render/${NAME}rocket
rm -rf $OUT
PX_LIGHT=punchy PX_NO_GROUND=1 nice -n 15 blender -b artsrc/units/meshes/$UNIT.blend -P artsrc/units/vehicles/render_v2_rocket.py -- $OUT $NAME $2 | grep -E "rocket centre|rendered"
for a in $NAME $NAME-climb $NAME-dive; do
	python3 artsrc/units/pack_sprites.py $OUT/$a mods/rapx/bits/hd/fx/missile-$a.png
done
