#!/bin/bash
# Builds the music player's track covers from the user's 3x3 cover sheet assets/audio/tracks_cover/covers-grid.png.
# Writes mods/rapx/music-covers/<track>.png (640x360, sharp), <track>-blur.png (backdrop) and
# <track>-card.png (640x237, the top of the cover: the track cards are 2.7:1 and this leaves out the printed title).
# <track> is the music.yaml file name (ra|audio/<track>.mp3). The older covers cut from video
# frames are made by make_covers_from_clips.sh.
set -e
S=$(cd "$(dirname "$0")" && pwd)
SRC=$S/../../assets/audio/tracks_cover/covers-grid.png
OUT=$S/../../mods/rapx/music-covers
mkdir -p "$OUT"
# Tile edges in the 1024x572 sheet (dark gutters between tiles are left out)
X=(2 343 686)
Y=(0 191 383)
W=337; H=188
# track|column|row   (the title printed on each tile)
COVERS=(
"sector4|0|0"      # Sector Four Lockdown
"siege|1|0"        # Desolate Siege
"perimeter|2|0"    # Fortress Defense
"crown|0|1"        # Claim the Crown
"ironrock|1|1"     # Kinetic Boundary
"calcsiege|2|1"    # Calculated Siege
"armoredpulse|0|2" # Armored Pulse
"frontier|1|2"     # Frontier Engagement
"gambit|2|2"       # Midnight War Room
)
for c in "${COVERS[@]}"; do
  IFS='|' read -r track col row <<< "$c"
  ffmpeg -hide_banner -loglevel error -y -i "$SRC" -frames:v 1 \
    -vf "crop=$W:$H:${X[$col]}:${Y[$row]},scale=640:360:flags=lanczos,unsharp=5:5:0.5" "$OUT/$track.png"
  ffmpeg -hide_banner -loglevel error -y -i "$OUT/$track.png" \
    -vf "scale=160:90,gblur=sigma=6,scale=256:144:flags=bicubic,eq=brightness=-0.12:saturation=1.3" "$OUT/$track-blur.png"
  ffmpeg -hide_banner -loglevel error -y -i "$OUT/$track.png" -vf "crop=640:237:0:0" "$OUT/$track-card.png"
  echo "$track <- tile $col,$row"
done
