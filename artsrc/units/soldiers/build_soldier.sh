#!/bin/sh
# Renders every game animation of a 3D soldier from its Mixamo clips (anim/<id>/*.fbx) and packs them into
# mods/rapx/bits/hd/soldiers/<id>/. Rerun with only some sequence names to redo just those.
#   artsrc/units/soldiers/build_soldier.sh e1 [sequence ...]
# Then: python3 artsrc/units/soldiers/write_sequences.py
cd "$(dirname "$0")/../../.." || exit 1
ID=$1; shift
A=artsrc/units/soldiers/anim/$ID
# Soldiers without their own Mixamo clips use e1's (his body goes onto e1's rig, see render_soldier.py)
[ -d "$A" ] || A=artsrc/units/soldiers/anim/e1
R=artsrc/units/soldiers/render/$ID
B=mods/rapx/bits/hd/soldiers/$ID
S=${SAMPLES:-40}
# sequence | clip | frames | options (PX_INPLACE / PX_SHOTS / PX_DEG) | facings
TABLE="
idle|idle|auto:8||32
look|look|auto:8||32
aim|aim|1||32
run|run|auto:8|PX_INPLACE=1|32
shoot|aim|auto:6|PX_SHOTS=0,1,0,0,1,0|32
liedown|toprone|span:6||16
standup|standup|span:6||16
crawl|crawl|auto:8|PX_INPLACE=1|16
proneshoot|pronefire|auto:6|PX_SHOTS=0,1,0,0,1,0|16
die1|death1|span:10|PX_INPLACE=1 PX_DEG=135|1
die2|death2|span:10|PX_INPLACE=1 PX_DEG=135|1
"
# Frame budget (2026-10-31): the constantly seen moves (stand, idle, run, shoot) get 32 directions, the brief
# under-fire set (dive, get up, crawl, prone fire) 16. Soldiers who never shoot skip the shooting moves.
UNARMED=" e6 medi mech spy "
echo "$TABLE" | while IFS='|' read -r seq clip frames opts facings; do
	[ -z "$seq" ] && continue
	if [ $# -gt 0 ] && ! echo " $* " | grep -q " $seq "; then continue; fi
	case "$UNARMED" in *" $ID "*) case $seq in shoot|proneshoot) continue ;; esac ;; esac
	# Resume: skip a move that is already fully rendered with this plan and packed
	case $frames in auto:*|span:*) n=${frames#*:} ;; *) n=$(echo "$frames" | tr ',' '\n' | wc -l | tr -d ' ') ;; esac
	want=$((n * facings))
	have=$(ls "$R/$seq" 2>/dev/null | grep -c png)
	if [ "$have" -eq "$want" ] && [ -f "$B/$seq.png" ] && [ -z "$FORCE" ]; then
		echo "== $ID $seq already done ($have frames), skipped"
		continue
	fi
	rm -rf "$R/$seq"
	echo "== $ID $seq ($clip, $frames, $facings facings)"
	env $opts blender -b -P artsrc/units/soldiers/render_soldier.py -- "$ID" "$A/$clip.fbx" "$R/$seq" "$facings" "$frames" "$S" 2>&1 | grep -E "rendered|Error"
	python3 artsrc/units/soldiers/pack_soldier.py "$R/$seq" "$B/$seq.png"
done
