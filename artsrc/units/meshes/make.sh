#!/bin/sh
# Turns AI-generated unit models (artsrc/units/meshes/glb/<id>.glb) into game sprites.
#   sh artsrc/units/meshes/make.sh <id> [<id> ...]        (from the repo root; ~3 minutes per body-only unit)
#   PX_RENDER_ONLY=1 sh artsrc/units/meshes/make.sh <id>  re-renders the existing <id>.blend (no import or turret
#                                                         split, so the Offsets in rules/vehicles.yaml stay valid)
# Ground vehicles render with PX_LIGHT=punchy (render_sprites.py); afterwards run artsrc/fx/make_wreck_fx.py.
#
# The models come from either route:
#   local:  hunyuan_local.py (shape) + project_texture.py (concept image projected on; writes <id>.projected)
#   online: hunyuan_generate.py (Hunyuan3D-2.1 Space, textured by the AI; ~1 unit/day on the free quota)
# Units made from downloaded Sketchfab models (sketchfab_models.py) are handed to make_sketchfab.py; their old
# AI models and sprites are kept in old-ai/. Credits: mods/rapx/CREDITS.
# Per unit: length in Blender units (classic size x 1.25), frame size.
set -e
cd "$(dirname "$0")/../../.."
BLENDER=${BLENDER:-blender}
DIR=artsrc/units/meshes

for id in "$@"; do
	if python3 $DIR/make_sketchfab.py --has "$id"; then
		python3 $DIR/make_sketchfab.py "$id"
		continue
	fi
	# Projected models already face +Y and carry the concept's colours; Space models face -Y and get a
	# saturation boost. Units marked "special" also need a turret split, spinner or animation pass
	# before they can replace their current sprites.
	if [ -f $DIR/glb/$id.projected ]; then YAW=0; SAT=1.0; else YAW=180; SAT=1.3; fi
	VAL=1.08
	TURRET=""  # "cx cy rx ry z_cut" for split_turret.py: hull frames 0-31 + turret (or spinner) 32+
	SPIN=32    # frames of a spinner loop
	FIX=0      # extra yaw (degrees) when the model's nose does not end up facing +Y
	AIR=""     # aircraft: no ground shadow (the engine draws it)
	case $id in
		apc)  LEN=7.75;  FRAME=192 ;;
		arty) LEN=8.25;  FRAME=192; VAL=0.8 ;;  # projection came out paler than the concept
		truk) LEN=8.1;   FRAME=192 ;;
		dtrk) LEN=8.1;   FRAME=192 ;;
		mcv)  LEN=10.7;  FRAME=224 ;;
		mnly) LEN=8.1;   FRAME=192 ;;
		ctnk) LEN=8.25;  FRAME=192 ;;
		# special: turret split (1tnk 2tnk 3tnk 4tnk jeep ftrk), spinner (mrj mgg ttnk),
		# empty launcher (v2rl), harvest/dock animation (harv)
		1tnk) LEN=7.5;   FRAME=192; VAL=0.8; TURRET="0 -1.4 1.55 1.65 1.9" ;;
		2tnk) LEN=8.6;   FRAME=192; VAL=0.8; TURRET="0 -1.1 1.95 2.35 1.95" ;;
		3tnk) LEN=9.1;   FRAME=192; TURRET="0 -0.2 1.95 1.95 3.1" ;;  # now Sketchfab (old-ai/3tnk)
		4tnk) LEN=10.5;  FRAME=224; TURRET="0 -0.7 2.9 2.4 2.55" ;;
		jeep) LEN=6.25;  FRAME=160; VAL=0.8; TURRET="0 0 0.65 0.7 3.1" ;;
		scar) LEN=6.5;   FRAME=160 ;;  # Spy Car (rules/spycar.yaml), jeep size class
		scr2) LEN=6.3;   FRAME=160 ;;  # Spy Car 2 (rules/spycar.yaml), jeep size class
		ftrk) LEN=8.1;   FRAME=192; TURRET="0 -1.9 1.45 1.75 3.15" ;;
		mrj)  LEN=8.1;   FRAME=224; VAL=0.8; TURRET="0 -1.5 4.8 1.1 3.6 0" ;;
		mgg)  LEN=8.1;   FRAME=192; SPIN=8; VAL=0.8; TURRET="0 -0.85 1.15 1.25 4.9 0" ;;
		# Prism Tank: the Gap Generator concept/model (glb/ptnk.glb = copy of glb/mgg.glb), whole column turns
		ptnk) LEN=8.1;   FRAME=224; VAL=0.8; TURRET="0 -0.85 1.35 1.45 2.6 0" ;;
		ttnk) LEN=8.75;  FRAME=192; TURRET="0 -1.2 1.85 2.15 2.7" ;;
		v2rl) LEN=9.75;  FRAME=224; TURRET="0 0 1.5 7.0 3.1 0" ;;  # the rocket, hidden while reloading
		harv) LEN=13.6;  FRAME=224 ;;
		lsat) LEN=2.6;   FRAME=192; AIR=1 ;;  # IDEA-16 Laser Satellite (project_texture --wide; LEN = body, wings span ~3x)
		ptnk) LEN=8.8;   FRAME=192; TURRET="0 0 1.5 1.8 2.95" ;;  # Prism Tank: the crystal block is the turret
		# Jets (assets/jets/<id>.png): length compressed from the real one (fighter ~7 units)
		af-16-fighting-kestrel) LEN=7.0; FRAME=192; AIR=1 ;;
		ab-2-wraith)            LEN=6.5; FRAME=256; AIR=1 ;;  # project_texture --wide
		tv-160-swanwing)        LEN=14;  FRAME=288; AIR=1; FIX=180 ;;  # project_texture --view 225,35
		af-104-starflash)       LEN=7.2; FRAME=160; AIR=1 ;;
		af-4-spectre-ii)        LEN=7.8; FRAME=160; AIR=1 ;;
		af-14-bobcat)           LEN=7.8; FRAME=160; AIR=1 ;;
		aa-10-thunderhog)       LEN=7.1; FRAME=160; AIR=1; FIX=90 ;;
		af-117-nightjar)        LEN=8.0; FRAME=160; AIR=1; FIX=90 ;;
		sr-7-blackwing)         LEN=10.7; FRAME=160; AIR=1 ;;
		ab-52-stratoforce)      LEN=13.6; FRAME=224; AIR=1; FIX=90 ;;
		af-22-raptorex)         LEN=7.7; FRAME=160; AIR=1 ;;
		ayf-23-black-recluse)   LEN=8.1; FRAME=160; AIR=1; FIX=180 ;;
		ax-47-stingray)         LEN=5.8; FRAME=160; AIR=1 ;;
		harrow)                 LEN=6.5; FRAME=160; AIR=1 ;;
		mirago-2000)            LEN=6.6; FRAME=160; AIR=1 ;;
		rafal-f4)               LEN=6.8; FRAME=160; AIR=1; FIX=90 ;;
		typhon)                 LEN=7.0; FRAME=160; AIR=1; FIX=90 ;;
		volcan)                 LEN=10.1; FRAME=160; AIR=1; FIX=90 ;;
		sea-vixa)               LEN=7.2; FRAME=160; AIR=1; FIX=90 ;;
		mik-3-strela)           LEN=4.7; FRAME=160; AIR=1; FIX=90 ;;
		lav-11-fang)            LEN=4.8; FRAME=160; AIR=1; FIX=90 ;;
		mik-21-fishbone)        LEN=6.6; FRAME=160; AIR=1 ;;
		mik-23-flintlock)       LEN=7.2; FRAME=160; AIR=1 ;;
		mik-25-foxbane)         LEN=7.9; FRAME=160; AIR=1 ;;
		sk-25-rook)             LEN=6.9; FRAME=160; AIR=1; FIX=90 ;;
		sk-27-flankard)         LEN=8.5; FRAME=160; AIR=1; FIX=90 ;;
		sk-35-flankard-e)       LEN=8.5; FRAME=160; AIR=1; FIX=90 ;;
		sk-47-berkov)           LEN=8.6; FRAME=160; AIR=1 ;;
		yk-141-freestyler)      LEN=7.6; FRAME=160; AIR=1 ;;
		grom-k)                 LEN=6.4; FRAME=160; AIR=1 ;;
		l-39u-albatross)        LEN=5.9; FRAME=160; AIR=1 ;;
		jx-20-jade-dragon)      LEN=8.1; FRAME=160; AIR=1 ;;
		swarm-drone)            LEN=3.5; FRAME=160; AIR=1 ;;
		saeqa)                  LEN=6.7; FRAME=160; AIR=1 ;;
		qahir-x)                LEN=5.9; FRAME=160; AIR=1 ;;
		zeppelin)               LEN=20; FRAME=288; AIR=1 ;;
		kestrel-tiltrotor)      LEN=7.4; FRAME=160; AIR=1 ;;
		an-225-dreamer)         LEN=18.9; FRAME=288; AIR=1 ;;
		*) echo "no settings for $id in $0" >&2; exit 1 ;;
	esac
	YAW=$((YAW + FIX))
	if [ -n "$AIR" ]; then export PX_NO_GROUND=1; unset PX_LIGHT; else unset PX_NO_GROUND; export PX_LIGHT=punchy; fi
	# Jets are 2.6x bigger in game (Balanced RTS proportions, artsrc/jets/make_jets.py JET_SCALE): render them
	# 2.6x bigger too (same framing, 2.6x the pixels) so they stay sharp at 1/3 scale. Not the Laser Satellite.
	if [ -n "$AIR" ] && [ "$id" != lsat ]; then
		export PX_UNIT_PX=9.1; FRAME=$((FRAME * 26 / 10))
	else
		unset PX_UNIT_PX
	fi
	[ -z "$PX_RENDER_ONLY" ] && "$BLENDER" -b -P $DIR/import_glb.py -- $DIR/glb/$id.glb $DIR/$id.blend $LEN $YAW $SAT $VAL
	rm -f $DIR/$id.blend1 && rm -rf $DIR/render/$id
	if [ $id = harv ]; then
		# Ore truck: full/half/empty sheets with harvest + dock animations, and the two wrecks
		"$BLENDER" -b $DIR/$id.blend -P $DIR/render_harv_mesh.py -- $DIR/render/harv 48
		for image in harv harvhalf harvempty hhusk hhusk2; do
			python3 artsrc/units/pack_sprites.py $DIR/render/harv/$image mods/rapx/bits/hd/units/$image.png
		done
		continue
	fi
	if [ -n "$TURRET" ]; then
		if [ -z "$PX_RENDER_ONLY" ]; then
			# Prints the Turreted Offset for rules/vehicles.yaml
			"$BLENDER" -b $DIR/$id.blend -P $DIR/split_turret.py -- $DIR/$id.blend $TURRET | grep -E "Offset|pivot"
			rm -f $DIR/$id.blend1
		fi
		if [ $id = v2rl ]; then
			[ -z "$PX_RENDER_ONLY" ] && "$BLENDER" -b $DIR/$id.blend -P $DIR/rocket_part.py | grep ready
			"$BLENDER" -b $DIR/$id.blend -P artsrc/units/vehicles/render_vehicle.py -- v2rl $DIR/render/$id $FRAME 48
		else
			PX_SPIN_FRAMES=$SPIN "$BLENDER" -b $DIR/$id.blend -P artsrc/units/tanks/render_tank.py -- $DIR/render/$id $FRAME 48
		fi
	else
		"$BLENDER" -b $DIR/$id.blend -P artsrc/units/render_sprites.py -- Body $DIR/render/$id 32 $FRAME 48
	fi
	python3 artsrc/units/pack_sprites.py $DIR/render/$id mods/rapx/bits/hd/units/$id.png
	# Prism art is painted blue: turn the paint into team-colour green
	[ $id = ptnk ] && python3 artsrc/space/team_paint.py mods/rapx/bits/hd/units/$id.png
done
