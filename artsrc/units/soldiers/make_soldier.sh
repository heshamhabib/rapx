#!/bin/sh
# One soldier through the whole 3D pipeline, no Mixamo work (his body goes onto e1's rig):
# empty-handed views (ChatGPT, from his concept assets/units/<id>.png) -> 3D body (Hunyuan3D) -> rig-ready body
# -> all animations at 32 facings (throttled) -> game sequences.
#   sh artsrc/units/soldiers/make_soldier.sh <id> "<what he wears, for the view prompts>"
# Weapon props: render_soldier.py PROPS (rifle by default, None = empty hands).
cd "$(dirname "$0")/../../.." || exit 1
ID=$1
DESC=${2:-"same uniform, gear and helmet"}
P=artsrc/prompts
python3 - "$ID" "$DESC" <<'EOF'
import re, sys
uid, desc = sys.argv[1], sys.argv[2]
p = "artsrc/prompts/soldier-views-prompts.md"
s = open(p).read()
if f"views/{uid}-unarmed-front" in s:
    sys.exit(0)
n = max(int(x) for x in re.findall(r"^### (\d+)\.", s, re.M))
common = (f"Exactly the same soldier as in the attached reference image ({desc}, and the same pure bright green (#00FF00) "
          "team-colour patches), but carrying NO weapon: both hands empty and open, nothing in the hands or on the shoulders. "
          "Neutral A-pose (arms slightly away from the body, legs apart). Full body, orthographic, whole figure visible, same scale "
          "and proportions as the reference. Realistic proportions, highly detailed, realistic physically based materials. Neutral "
          "even studio lighting. Use no green anywhere except the team-colour patches. Isolated on a flat plain white background, "
          "no ground shadow, no text, no logo, no watermark. Portrait image (3:4).")
views = [("front", "Seen from the front, facing the camera. "),
         ("back", "Seen from directly BEHIND: we see his back and the backs of the legs; his face and front are hidden. "),
         ("left", "Seen exactly from his LEFT side (side profile, he faces the left edge of the image). ")]
add = [""]
for i, (v, txt) in enumerate(views):
    add += [f"### {n + 1 + i}. {uid} - unarmed {v}", f"Save as: `views/{uid}-unarmed-{v}.png`",
            f"Reference: `assets/units/{uid}.png`", "", "```", txt + common, "```", ""]
open(p, "w").write(s.rstrip("\n") + "\n" + "\n".join(add))
print("added view prompts for", uid)
EOF
( cd $P && python3 generate_images.py --prompts soldier-views-prompts.md --category units \
    --only views/$ID-unarmed-front,views/$ID-unarmed-back,views/$ID-unarmed-left --stop-on-limit ) || exit 1
# One GPU job at a time: wait for any other soldier render
while pgrep -f "build_soldier[.]sh" >/dev/null; do sleep 20; done
[ -f artsrc/units/meshes/shape/$ID-unarmed-front.glb ] || ~/rapx3d/venv/bin/python artsrc/units/meshes/hunyuan_local.py $ID-unarmed-front || exit 1
blender -b -P artsrc/units/soldiers/prep_mixamo.py -- $ID 2>&1 | grep -E "prepared|Error"
sh artsrc/units/soldiers/build_soldier.sh $ID
python3 artsrc/units/soldiers/write_sequences.py
echo "$ID done"
