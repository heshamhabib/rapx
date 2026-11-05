#!/bin/bash
# Older version: builds the track covers from video frames in assets/audio/tracks_cover (replaced by make_covers.sh).
# Writes mods/rapx/music-covers/<track>.png (640x360, sharp) and <track>-blur.png (backdrop).
# <track> is the music.yaml file name (ra|audio/<track>.mp3). Re-run after changing the list.
set -e
S=$(cd "$(dirname "$0")" && pwd)
SRC=$S/../../assets/audio/tracks_cover
OUT=$S/../../mods/rapx/music-covers
mkdir -p "$OUT"
# track|clip (prefix match)|second   (the gemini clips have rounded corners, so every frame is cropped 6%)
COVERS=(
"sector4|Missile_launches_in_storm|3.2"
"crown|gemini_generated_video_51e521d4|0.8"
"perimeter|Futuristic_gunship_attacking|6.0"
"siege|Armored_truck_transforms|5.6"
"ironrock|Soldier_and_tank_battle_war|1.2"
"armoredpulse|Armored_truck_transforms|3.0"
"calcsiege|Missile_launches_in_storm|5.6"
"frontier|gemini_generated_video_9c875172|3.0"
"gambit|Soldier_sprints_and_returns_fire|6.0"
)
for c in "${COVERS[@]}"; do
  IFS='|' read -r track clip t <<< "$c"
  f=$(ls "$SRC/$clip"*.mp4 | head -1)
  ffmpeg -hide_banner -loglevel error -y -ss "$t" -i "$f" -frames:v 1 \
    -vf "crop=iw*0.94:ih*0.94,scale=640:360:flags=lanczos,eq=contrast=1.05:saturation=1.08" "$OUT/$track.png"
  ffmpeg -hide_banner -loglevel error -y -i "$OUT/$track.png" \
    -vf "scale=160:90,gblur=sigma=6,scale=256:144:flags=bicubic,eq=brightness=-0.12:saturation=1.3" "$OUT/$track-blur.png"
  echo "$track <- $(basename "$f") @ ${t}s"
done
