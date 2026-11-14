#!/bin/sh
# Non-humanoid units ("Other (own approach)": Enforcer Walker, Strider, Spider Drone, Attack Dog) from their
# downloaded Sketchfab models (render_creature.py CFG), throttled, one after another, then sequences and cameos.
#   sh artsrc/units/soldiers/make_creatures.sh [enfw strd sdrn dog]
cd "$(dirname "$0")/../../.." || exit 1
while pgrep -f "build_soldier[.]sh|make_robots[.]sh" >/dev/null; do sleep 60; done
S=${SAMPLES:-40}
for ID in ${*:-enfw strd sdrn dog}; do
	echo "===== $ID ($(date +%H:%M))"
	IDLE=1; case $ID in enfw|dog) IDLE=auto:8 ;; esac
	RUN=auto:8
	for spec in "idle|$IDLE||32" "aim|1||32" "run|$RUN||32" "shoot|auto:6||32" "die1|span:10|PX_DEG=135|1" "die2|span:10|PX_DEG=225|1"; do
		seq=${spec%%|*}; rest=${spec#*|}; frames=${rest%%|*}; rest=${rest#*|}; opts=${rest%%|*}; facings=${rest#*|}
		R=artsrc/units/soldiers/render/$ID/$seq
		case $frames in auto:*|span:*) n=${frames#*:} ;; *) n=$(echo "$frames" | tr ',' '\n' | wc -l | tr -d ' ') ;; esac
		if [ "$(ls $R 2>/dev/null | grep -c png)" -eq $((n * facings)) ] && [ -f mods/rapx/bits/hd/soldiers/$ID/$seq.png ]; then
			echo "== $ID $seq already done"; continue
		fi
		rm -rf $R
		echo "== $ID $seq ($frames, $facings facings)"
		env $opts nice -n 10 blender -b -P artsrc/units/soldiers/render_creature.py -- $ID $seq $R $facings $frames $S 2>&1 | grep -E "^rendered|Error"
		python3 artsrc/units/soldiers/pack_soldier.py $R mods/rapx/bits/hd/soldiers/$ID/$seq.png
	done
	python3 artsrc/units/soldiers/write_sequences.py >/dev/null
	PX_THROTTLE=0 PX_CAMEO=$PWD/assets/units/renders/$ID.png nice -n 10 blender -b -P artsrc/units/soldiers/render_creature.py -- \
		$ID aim /tmp/unused 1 1 128 2>&1 | grep -E "^cameo"
	echo "$ID done"
done
# SKIP_ICONS=1: leave the full cameo pass out (update single icons by hand instead)
[ -z "$SKIP_ICONS" ] && PATH="$HOME/.dotnet:$PATH" DOTNET_ROOT="$HOME/.dotnet" python3 artsrc/px-cameos/generate.py | tail -1
echo "===== all done ($(date +%H:%M))"
