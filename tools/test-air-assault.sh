#!/bin/sh
# Air assault test (IDEA-47: PxAirAssault, PxSmokeScreen, WithPxRotorWash): starts a skirmish on Agenda with a
# Chinook and six riflemen east of your base. The riflemen board, the Chinook flies four cells and gets the
# ordinary Unload order (F), which must make it hover and fast-rope; screenshots follow it: smoke rounds, rotor wash, ropes, soldiers sliding down,
# ropes cut loose. Shots land in ~/Library/Application Support/OpenRA/Screenshots/rapx/<version>/.
#
#   sh tools/test-air-assault.sh          (from the repo root)
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
[ -f "${SKIRMISH}" ] && cp "${SKIRMISH}" "${SKIRMISH}.before-assault"
[ -f "${SETTINGS}" ] && cp "${SETTINGS}" "${SETTINGS}.before-assault"
restore() {
	if [ -f "${SKIRMISH}.before-assault" ]; then mv "${SKIRMISH}.before-assault" "${SKIRMISH}"; else rm -f "${SKIRMISH}"; fi
	if [ -f "${SETTINGS}.before-assault" ]; then mv "${SETTINGS}.before-assault" "${SETTINGS}"; fi
}
trap restore EXIT INT TERM

# Agenda, you on spawn 1 (36,48), one easy bot far away on spawn 2 (92,48)
python3 - "${SKIRMISH}" "${AGENDA}" <<'PYEOF'
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
PYEOF

# A Chinook on the ground with six riflemen beside it
export RAPX_SPAWN="tran@+6,+1;e1@+4,+0;e1@+4,+1;e1@+4,+2;e1@+5,+0;e1@+5,+2;e1@+3,+1"

# launch-game-test.sh starts the game at 20 s; the world is loaded by about 35 s. Board at 38 s, take off and fly
# four cells at 43 s, then the ordinary Unload order (what F sends) at 47 s: it must hover and fast-rope, not land. Shots follow it
# Clear skies, so fog or a blizzard does not hide the ropes
export RAPX_WEATHER=Clear
export RAPX_TEST_EXTRA="37000:focus tran 1.5;38000:select e1;38300:board tran;43000:order Move tran +10,+1;\
43200:follow tran;47000:order Unload tran +0,+0;47600:shot;48600:shot;49600:shot;50400:shot;51200:shot;52000:shot;\
52800:shot;53800:shot;55000:shot;57000:shot;60000:quit"

sh "${ROOT}/launch-game-test.sh" --start
