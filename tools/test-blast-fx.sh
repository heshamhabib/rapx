#!/bin/sh
# Blast FX test range (cinematic combat FX: PxExplosion v2, PxBlastWaves, WithPxBlastDeath): starts a skirmish on
# Agenda with a platoon of riflemen, grenadiers and rocket soldiers standing in a cluster east of your base, then
# detonates a tank shell, an artillery round and a V2 among them while taking screenshots, so the fireball, dust and
# shock waves, debris and the soldiers thrown by the blast can be checked. Shots land in
# ~/Library/Application Support/OpenRA/Screenshots/rapx/<version>/.
#
#   sh tools/test-blast-fx.sh          (from the repo root)
#
# Your saved skirmish lobby and settings.yaml are backed up and restored when the game closes.
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SUPPORT_DIR="${HOME}/Library/Application Support/OpenRA"
SKIRMISH="${SUPPORT_DIR}/skirmish.rapx.yaml"
SETTINGS="${SUPPORT_DIR}/settings.yaml"
AGENDA=f3313186a1cab4f936e8ae0aa45954d99e10fafe

mkdir -p "${SUPPORT_DIR}"
[ -f "${SKIRMISH}" ] && cp "${SKIRMISH}" "${SKIRMISH}.before-blast"
[ -f "${SETTINGS}" ] && cp "${SETTINGS}" "${SETTINGS}.before-blast"
restore() {
	if [ -f "${SKIRMISH}.before-blast" ]; then mv "${SKIRMISH}.before-blast" "${SKIRMISH}"; else rm -f "${SKIRMISH}"; fi
	if [ -f "${SETTINGS}.before-blast" ]; then mv "${SETTINGS}.before-blast" "${SETTINGS}"; fi
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

# A platoon in a tight cluster around +8,+1 (relative to your start), a medic in the middle to focus on, two tanks and
# a jeep beside them to see the shove; a second cluster at +8,+6 for the V2
PLATOON="medi@+8,+1;e1@+7,+0;e1@+9,+0;e1@+7,+2;e1@+9,+2;e2@+8,+0;e2@+8,+2;e3@+6,+1;e3@+10,+1;e1@+6,+0;e1@+10,+2;e2@+6,+2;e3@+10,+0"
ARMOUR="2tnk@+11,+1;1tnk@+5,+1;jeep@+8,+3"
PLATOON2="e1@+7,+6;e1@+9,+6;e1@+8,+5;e1@+8,+7;e2@+7,+7;e2@+9,+5;e3@+6,+6;e3@+10,+6"
export RAPX_SPAWN="${PLATOON};${ARMOUR};${PLATOON2}"

# launch-game-test.sh clicks through the menus and starts the game at 20 s; the world is loaded by about 35 s.
# Tank shell at 42 s, artillery at 48 s, V2 at 55 s; shots through each blast; quit well after the last shot
export RAPX_TEST_EXTRA="40000:focus medi 2;42000:boom 120mm +8,+1;42200:shot;42600:shot;43100:shot;44000:shot;45500:shot;48000:boom ArtilleryExplode +8,+1;48200:shot;48700:shot;49300:shot;50200:shot;52000:shot;55000:boom V2Explode +8,+6;55200:shot;55700:shot;56300:shot;57200:shot;59000:shot;61000:shot;65000:quit"

sh "${ROOT}/launch-game-test.sh" --start
