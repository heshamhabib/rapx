#!/bin/bash
# Builds the intro trailer from the Google Flow clips in assets/inbox/{videos,new_videos},
# cut to assets/audio/Iron_rock.mp3, then converts it into mods/rapx/movies/intro.rpv.
#
# Outputs (next to this script):
#   intro-game.mp4     no closing fade: the in-game Barrage transition plays over the end
#   intro-preview.mp4  same cut with a fade to black, for sharing
set -e
S=$(cd "$(dirname "$0")" && pwd)
cd "$S/../../assets"
V=inbox/videos
N=inbox/new_videos
GAME=$S/intro-game.mp4
PREVIEW=$S/intro-preview.mp4

# Music starts at track 10.4s, so in video time: drop @5.6, chorus @37.6, quiet section @71.6,
# second chorus @101.6, its mid hit @118.6, its end @134.1 (where the finale blast lands).
MUSIC_START=10.4
LOGO_HOLD=6

# file|start|duration
SEG=(
"$V/Missile_launches_in_storm_10cad684.mp4|0|9.6"
"$V/Sci-fi_world_war_space_laser_08f62e02.mp4|0|8"
"intro_assets/stealth_fighter_blue.mp4|0|8"
"$V/Prism_tanks_battling_enemy_armor_09b5a890.mp4|0|8"
"$V/Tanks_fighting_in_futuristic_war_4f43d2b2.mp4|4|4"
"$V/Sci-fi_world_war_space_laser_91163795.mp4|0|8"
"$V/Superpowers_power_plants_in_conf…_a62a15a7.mp4|4|4"
"$(ls $V/Futuristic_gunship_attacking_mil*_41406968.mp4)|0|8"
"$N/Railgun_robot_aims_and_fires_5a7497e7.mp4|0|8"
"$N/Mech_battle_on_giant_battlefield_d4233254.mp4|2|6"
# quiet section
"$N/Walker_tank_emerges_from_factory_8ae6f709_t3.4-8.mp4|0|4.6"
"$N/Armored_airship_over_burning_city_9e7b9049.mp4|0|6"
"$N/Mech_and_robot_activate_in_8cf6edd8_t2.1-8.mp4|0|5.9"
"$N/Soldier_drops_from_hovering_gunship_39925504.mp4|0|7.5"
"$N/Submarine_breaks_through_arctic_ice_4a754814.mp4|0|6"
# second chorus
"$N/Jet_streaks_past_and_bombs_8f61d038.mp4|0|6"
"$N/Robot_ambushes_soldier_in_street_5f3cbdca.mp4|0|8"
"$(ls $N/Helicopter_attacking_airship_in_*_ac304ff5.mp4)|3|3"
"$N/APC_fires_rocket_salvo_80bd18c9.mp4|0|6"
"$V/Tanks_fighting_in_futuristic_war_4f43d2b2.mp4|0|4"
"$V/Sci-fi_factions_clash_in_war_76b68cb0.mp4|0|8"
)

IN=(); FC=""; CAT=""; T=0
for i in "${!SEG[@]}"; do
	IFS='|' read -r f st du <<< "${SEG[$i]}"
	end=$(echo "$st+$du" | bc)
	IN+=(-i "$f")
	# Low-res (360p) clips get a Lanczos upscale plus light sharpening
	h=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$f")
	sharpen=""; [ "$h" -lt 720 ] && sharpen=",unsharp=5:5:0.7"
	FC+="[$i:v]trim=$st:$end,setpts=PTS-STARTPTS,scale=1280:720:flags=lanczos$sharpen,fps=24,format=yuv420p,setsar=1[v$i];"
	FC+="[$i:a]atrim=$st:$end,asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:$du[a$i];"
	CAT+="[v$i][a$i]"
	T=$(echo "$T+$du" | bc)
done
NSEG=${#SEG[@]}
TOT=$(echo "$T+$LOGO_HOLD" | bc)
echo "clips end at ${T}s, total ${TOT}s"

ffmpeg -hide_banner -loglevel error -y "${IN[@]}" \
	-loop 1 -framerate 24 -t $LOGO_HOLD -i "$S/logo-hold.png" \
	-ss $MUSIC_START -t $TOT -i audio/Iron_rock.mp3 -filter_complex "
	$FC
	[$NSEG:v]scale=3840:-1,zoompan=z='1+0.08*on/($LOGO_HOLD*24)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1280x720:fps=24,trim=0:$LOGO_HOLD,format=yuv420p,setsar=1[vL];
	anullsrc=r=48000:cl=stereo,atrim=0:$LOGO_HOLD[aL];
	${CAT}[vL][aL]concat=n=$((NSEG + 1)):v=1:a=1[vc][ac];
	[vc]fade=t=in:st=0:d=0.5,format=yuv420p[vout];
	[ac]volume=0.25[sfx];
	[$((NSEG + 1)):a]afade=t=in:d=0.3,afade=t=out:st=$(echo "$TOT-6" | bc):d=6[mus];
	[mus][sfx]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[aout]" \
	-map "[vout]" -map "[aout]" -c:v libx264 -preset slow -crf 12 -r 24 -c:a aac -b:a 256k -movflags +faststart "$GAME"

ffmpeg -hide_banner -loglevel error -y -i "$GAME" -vf "fade=t=out:st=$(echo "$TOT-1.5" | bc):d=1.5" \
	-c:v libx264 -preset slow -crf 17 -c:a copy -movflags +faststart "$PREVIEW"

# Game build: 1080p, best JPEG quality (Lanczos upscale avoids a pixelated look)
python3 "$S/../../tools/make-video.py" "$GAME" "$S/../../mods/rapx/movies/intro.rpv" --width 1920 --quality 2
