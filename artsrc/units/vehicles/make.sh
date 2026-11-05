#!/bin/sh
# Builds, renders and packs the support vehicles (classic frame layouts, see render_vehicle.py).
#   sh artsrc/units/vehicles/make.sh [ids...]        (from the repo root; ~2-4 minutes each)
set -e
cd "$(dirname "$0")/../../.."
BLENDER=${BLENDER:-blender}
DIR=artsrc/units/vehicles
IDS=${*:-jeep apc arty v2rl}

# One render at a time: parallel Blender processes crash while writing the shared Metal kernel cache
for id in $IDS; do
	"$BLENDER" -b -P $DIR/build_vehicles.py -- $id
	rm -f $DIR/$id.blend1 && rm -rf $DIR/render/$id
	"$BLENDER" -b $DIR/$id.blend -P $DIR/render_vehicle.py -- $id $DIR/render/$id 160 48
	python3 artsrc/units/pack_sprites.py $DIR/render/$id mods/rapx/bits/hd/units/$id.png
done
