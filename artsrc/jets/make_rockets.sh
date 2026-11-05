#!/bin/sh
# Renders the national rocket-launcher rockets (IDEA-17; kinds in ordnance.py) at the jets' scale (frame grows with length),
# into mods/rapx/bits/hd/fx/missile-<kind>.png (sequences: pxmissile in sequences/hd-missiles.yaml, used by
# weapons/rocket-launchers.yaml).
#   sh artsrc/jets/make_rockets.sh [kind ...]       (from the repo root; default: all)
set -e
cd "$(dirname "$0")/../.."
KINDS=${*:-"gmlrs_us gmlrs_uk gmlrs_fr gmlrs_de gmlrs_it trg300 fatah type12 k239 tos220 vilkha grad122 pinaka sakr phl16 fajr5 shard136"}
for k in $KINDS; do
	rm -rf artsrc/jets/render-missiles/$k
	nice -n 15 blender -b -t 4 -P artsrc/jets/render_missiles.py -- $k artsrc/jets/render-missiles/$k | grep rendered
	python3 artsrc/units/pack_sprites.py artsrc/jets/render-missiles/$k mods/rapx/bits/hd/fx/missile-$k.png
done
