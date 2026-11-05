#!/bin/sh
# Spy Car art: both cars are Sketchfab models (sketchfab_models.py: scar = DBS, scr2 = DB5), rendered by make.sh ->
# make_sketchfab.py at 2x pixels. A car without one falls back to a 3D model made from its concept (assets/units/).
# Both -> 32 facings -> game sequences. Waits for the soldier queue first (one GPU job at a time).
cd "$(dirname "$0")/../../.." || exit 1
while pgrep -f "queue_soldiers[.]sh" >/dev/null; do sleep 60; done
for ID in scar scr2; do
    if python3 artsrc/units/meshes/make_sketchfab.py --has $ID; then SKETCHFAB=1; else
        SKETCHFAB=
        ~/rapx3d/venv/bin/python artsrc/units/meshes/hunyuan_local.py $ID || exit 1
        ~/rapx3d/venv/bin/python artsrc/units/meshes/project_texture.py $ID | grep -E "view|fit"
    fi
    sh artsrc/units/meshes/make.sh $ID | grep -E "^packed"
    ID=$ID SKETCHFAB=$SKETCHFAB python3 - <<'PY'
import os
uid = os.environ["ID"]
# jeep size class: x0.76 of the normal vehicle scale (0.4667 for AI models, 0.2333 for the 2x Sketchfab renders)
scale = "0.1773" if os.environ.get("SKETCHFAB") else "0.3547"
p = "mods/rapx/sequences/hd-units.yaml"
s = open(p).read()
if f"\n{uid}:\n" not in s:
    s = s.rstrip("\n") + (f"\n\n# Spy Car (rules/spycar.yaml {uid.upper()}): artsrc/units/meshes/make_spycar.sh, jeep size class\n{uid}:\n"
                          f"\tidle:\n\t\tFilename: ra|bits/hd/units/{uid}.png\n\t\tFacings: 32\n\t\tUseClassicFacings: False\n"
                          f"\t\tScale: {scale}\n")
    open(p, "w").write(s)
# Drop this car's Jeep placeholder (the first RenderSprites: Image: jeep after its actor header)
p = "mods/rapx/rules/spycar.yaml"
s = open(p).read()
head = s.index(f"\n{uid.upper()}:\n")
end = s.find("\n\n", head + 1)
end = len(s) if end < 0 else end
block = s[head:end].replace("\tRenderSprites:\n\t\tImage: jeep", "").rstrip("\n")
s = s[:head] + block + s[end:]
open(p, "w").write(s)
PY
done
PATH="$HOME/.dotnet:$PATH" DOTNET_ROOT="$HOME/.dotnet" python3 artsrc/px-cameos/generate.py | tail -1
echo "spy cars done"
