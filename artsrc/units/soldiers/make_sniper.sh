#!/bin/sh
# The Sniper's art, start to finish (no Mixamo work: he goes onto e1's rig):
# concept + empty-handed views (ChatGPT) -> 3D body (Hunyuan3D) -> rig-ready body -> all animations at 32 facings
# -> game sequences, his own image (drops the e1 stand-in) and sidebar icon.
#   sh artsrc/units/soldiers/make_sniper.sh
cd "$(dirname "$0")/../../.." || exit 1
P=artsrc/prompts
( cd $P && python3 generate_images.py --prompts sniper-prompts.md --category units --ref ../../assets/units/e1.png --stop-on-limit ) || exit 1
( cd $P && python3 generate_images.py --prompts soldier-views-prompts.md --category units --only views/snip-unarmed-front,views/snip-unarmed-back,views/snip-unarmed-left --stop-on-limit ) || exit 1
# One GPU job at a time: wait for any other soldier render
while pgrep -f "build_soldier[.]sh" >/dev/null; do sleep 20; done
~/rapx3d/venv/bin/python artsrc/units/meshes/hunyuan_local.py snip-unarmed-front || exit 1
blender -b -P artsrc/units/soldiers/prep_mixamo.py -- snip 2>&1 | grep -E "prepared|Error"
sh artsrc/units/soldiers/build_soldier.sh snip
python3 artsrc/units/soldiers/write_sequences.py
# His own image now: drop the e1 stand-in, give him a sidebar icon from the concept
python3 - <<'EOF'
p = "mods/rapx/rules/infantry.yaml"
s = open(p).read()
s = s.replace("\tRenderSprites:\n\t\tImage: e1\n", "", 1)
s = s.replace("# Uses the Rifle Infantry's sprites until his own 3D art is rendered (artsrc/units/soldiers, image snip).\n",
              "# 3D art: artsrc/units/soldiers/make_sniper.sh (image snip).\n", 1)
open(p, "w").write(s)
p = "mods/rapx/sequences/robots.yaml"
s = open(p).read()
if "\nsnip:\n" not in s:
    s = s.rstrip("\n") + "\n\n# Sniper (rules/infantry.yaml SNIP): body sequences in hd-soldiers3d.yaml\nsnip:\n\ticon:\n\t\tFilename: ra|bits/hd/icons/snipcameo.png\n\t\tScale: 0.5\n"
    open(p, "w").write(s)
EOF
PATH="$HOME/.dotnet:$PATH" DOTNET_ROOT="$HOME/.dotnet" python3 artsrc/px-cameos/generate.py | tail -1
echo "sniper done"
