#!/bin/sh
# Renders the fired-weapon sprites (artsrc/jets/render_missiles.py) into mods/rapx/bits/hd/fx/missile-<kind>.png.
#   sh artsrc/jets/make_missiles.sh [kind ...]       (from the repo root; default: all)
set -e
cd "$(dirname "$0")/../.."
KINDS=${*:-"aim9 r73 aim120 r77 aim54 agm65 mk82 gbu hydra"}
for k in $KINDS; do
	rm -rf artsrc/jets/render-missiles/$k
	nice -n 15 blender -b -t 4 -P artsrc/jets/render_missiles.py -- $k artsrc/jets/render-missiles/$k | grep rendered
	python3 artsrc/units/pack_sprites.py artsrc/jets/render-missiles/$k mods/rapx/bits/hd/fx/missile-$k.png
done
