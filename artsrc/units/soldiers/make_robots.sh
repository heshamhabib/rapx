#!/bin/sh
# Humanoid robots (IDEA-29) through the 3D soldier pipeline, one after another (throttled, ~1 h each).
# Bodies: downloaded Sketchfab models prepared by prep_sketchfab.py into upload/<id>.blend (see the commands below),
# animated on e1's Mixamo rig (render_soldier.py FIT / RIGID). Robots never take cover: no prone moves, and the
# look-around idle is not used either.
#   SF=artsrc/units/soldiers/sketchfab; P=artsrc/units/soldiers/prep_sketchfab.py
#   blender -b -P $P -- cybt $SF/robot.cybt__*/scene.gltf "" --armbands
#   blender -b -P $P -- bdrd $SF/robot.rgun__*/scene.gltf "" --keep-near=1.7 --keep-r=1.0 --tpose=0.2,1.40,62 --armbands
#   blender -b -P $P -- rgun $SF/robot.rgun__*/scene.gltf "" --keep-near=-3.72 --keep-r=1.0 --tpose=0.33,1.31,62 --armbands
#   blender -b -P $P -- irgd $SF/robot.irgd__*/scene.gltf "" --armbands
#   blender -b -P $P -- taut $SF/robot.taut__heavy_robot/scene.gltf "" --yaw=90 --armbands
cd "$(dirname "$0")/../../.." || exit 1
while pgrep -f "build_soldier[.]sh" >/dev/null; do sleep 60; done
for ID in ${*:-cybt bdrd rgun irgd taut}; do
	echo "===== $ID ($(date +%H:%M))"
	sh artsrc/units/soldiers/build_soldier.sh $ID idle aim run shoot die1 die2 > artsrc/units/soldiers/render/$ID-chain.log 2>&1
	python3 artsrc/units/soldiers/write_sequences.py >/dev/null
	PX_THROTTLE=0 PX_CAMEO=$PWD/assets/units/renders/$ID.png nice -n 10 blender -b -P artsrc/units/soldiers/render_soldier.py -- \
		$ID artsrc/units/soldiers/anim/e1/aim.fbx /tmp/unused 1 1 128 2>&1 | grep -E "^cameo"
	echo "$ID done"
done
PATH="$HOME/.dotnet:$PATH" DOTNET_ROOT="$HOME/.dotnet" python3 artsrc/px-cameos/generate.py | tail -1
echo "===== all robots done ($(date +%H:%M))"
