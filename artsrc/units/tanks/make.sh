#!/bin/sh
# Builds, renders and packs the tanks (hull + turret sheets, classic frame layout).
#   sh artsrc/units/tanks/make.sh [ids...]        (from the repo root; default: all four, ~4 minutes each)
set -e
cd "$(dirname "$0")/../../.."
BLENDER=${BLENDER:-blender}
DIR=artsrc/units/tanks
IDS=${*:-1tnk 2tnk 3tnk 4tnk}

# One render at a time: parallel Blender processes crash while writing the shared Metal kernel cache
for id in $IDS; do
	FRAME=160
	[ "$id" = 4tnk ] && FRAME=192
	"$BLENDER" -b -P $DIR/build_tanks.py -- $id
	rm -f $DIR/$id.blend1 && rm -rf $DIR/render/$id
	"$BLENDER" -b $DIR/$id.blend -P $DIR/render_tank.py -- $DIR/render/$id $FRAME 48
	python3 artsrc/units/pack_sprites.py $DIR/render/$id mods/rapx/bits/hd/units/$id.png
done
