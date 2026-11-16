#!/bin/sh
# Air strike test range (cluster and white phosphorus bombs): starts a skirmish on Agenda with a ready scene.
#   You (USA, west spawn): a Radar Dome and an Airfield; four bombers already flying over your base: Su-25 (RBK-500
#   cluster bombs), B-52 (CBU-87 stream, then Mk 82s), Vulcan and Tu-160 (white phosphorus first, then bombs).
#   Bot (east, 14-18 cells away): infantry squads and light vehicles in the open, no air defence.
# Select a bomber and right-click the enemy group. Watch for: the dispensers opening in the air, the bomblet rain and
# its carpet of blasts; the phosphorus air burst, its fan of white smoke trails and the burning ground left behind.
# Test cheats (map revealed, instant build, unlimited power) come from launch-game-test.sh.
#
#   sh tools/test-airstrike.sh          (from the repo root)
#
# Your saved skirmish lobby and settings.yaml are backed up and restored when the game closes.
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SUPPORT_DIR="${HOME}/Library/Application Support/OpenRA"
SKIRMISH="${SUPPORT_DIR}/skirmish.rapx.yaml"
SETTINGS="${SUPPORT_DIR}/settings.yaml"
# The UID changes whenever the map is edited: compute it, a stale one silently loads another map
AGENDA=$(python3 "${ROOT}/tools/map_uid.py" "${ROOT}/mods/rapx/maps/agenda.oramap")

mkdir -p "${SUPPORT_DIR}"
[ -f "${SKIRMISH}" ] && cp "${SKIRMISH}" "${SKIRMISH}.before-airstrike"
[ -f "${SETTINGS}" ] && cp "${SETTINGS}" "${SETTINGS}.before-airstrike"
restore() {
	if [ -f "${SKIRMISH}.before-airstrike" ]; then mv "${SKIRMISH}.before-airstrike" "${SKIRMISH}"; else rm -f "${SKIRMISH}"; fi
	if [ -f "${SETTINGS}.before-airstrike" ]; then mv "${SETTINGS}.before-airstrike" "${SETTINGS}"; fi
}
trap restore EXIT INT TERM

# Agenda, you on spawn 1 (36,48), one easy bot on spawn 2 (92,48)
python3 - "${SKIRMISH}" "${AGENDA}" <<'EOF'
import os, sys
path, uid = sys.argv[1], sys.argv[2]
old = open(path).read().splitlines() if os.path.exists(path) else []
options = []
inside = False
for line in old:
    if line.startswith("Options:"):
        inside = True
        continue
    if inside and line.startswith("\t"):
        options.append(line)
        continue
    inside = False
out = ["Map: " + uid, "Options:"] + options + [
    "Player: Multi0", "\tColor: 1E3CD2", "\tFaction: usa", "\tSpawnPoint: 1", "\tTeam: 0", "\tHandicap: 0",
    "Bots:", "\teasy: Multi1", "\t\tColor: F25FA0", "\t\tFaction: turkey", "\t\tSpawnPoint: 2", "\t\tTeam: 0",
    "\t\tHandicap: 0"]
open(path, "w").write("\n".join(out) + "\n")
EOF

# Positions are relative to your start (36,48); @1 = the bot. Jets: x,y,health,facing,altitude
OURS="dome@+3,-6;afld@-7,-5;jet.su25@+2,-3,100,768,2048;jet.b52@+2,0,100,768,2048;jet.vulcan@+2,3,100,768,2048;jet.tu160@+2,6,100,768,2048"
THEIRS="e1@+15,-1@1;e1@+15,0@1;e1@+16,-1@1;e1@+16,0@1;e3@+15,1@1;e3@+16,1@1;e1@+17,-1@1;e1@+17,0@1;jeep@+16,3@1;apc@+17,4@1;jeep@+18,2@1;e1@+15,5@1;e1@+16,5@1;e3@+16,6@1"
export RAPX_SPAWN="${OURS};${THEIRS}"

sh "${ROOT}/launch-game-test.sh" --start
