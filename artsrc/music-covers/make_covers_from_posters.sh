#!/bin/bash
# Builds music player covers from the Facebook poster art in assets/audio/tracks_cover/posters (portrait images).
# Cuts a full-width 16:9 band out of each poster, below the logo and above the printed text, then writes
# mods/rapx/music-covers/<track>.png, <track>-blur.png and <track>-card.png like make_covers.sh.
set -e
S=$(cd "$(dirname "$0")" && pwd)
SRC=$S/../../assets/audio/tracks_cover/posters
OUT=$S/../../mods/rapx/music-covers
mkdir -p "$OUT"
# track|poster|top of the band as a fraction of the poster height
COVERS=(
"burningsand|egypt-pyramids.jpeg|0.40"    # Tides of Burning Sand
"lastbastion|capitol-siege.jpeg|0.42"     # Last Bastion Standing
"tideturn|pacific-dogfight.jpg|0.17"      # Turning of the Tide
"highground|mount-rushmore.jpeg|0.42"     # Hold the High Ground
"pinkignition|titans-godzilla-vs-kong.jpeg|0.33"  # Pink Ignition
"roardark|godzilla-roar-portrait.jpg|0.0"    # Roar in the Dark (landscape art: the band is most of it)
)
for c in "${COVERS[@]}"; do
  IFS='|' read -r track src top <<< "$c"
  ffmpeg -hide_banner -loglevel error -y -i "$SRC/$src" -frames:v 1 \
    -vf "crop=iw:iw*9/16:0:ih*$top,scale=640:360:flags=lanczos" "$OUT/$track.png"
  ffmpeg -hide_banner -loglevel error -y -i "$OUT/$track.png" \
    -vf "scale=160:90,gblur=sigma=6,scale=256:144:flags=bicubic,eq=brightness=-0.12:saturation=1.3" "$OUT/$track-blur.png"
  ffmpeg -hide_banner -loglevel error -y -i "$OUT/$track.png" -vf "crop=640:237:0:0" "$OUT/$track-card.png"
  echo "$track <- $src"
done
