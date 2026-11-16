#!/bin/sh
# Air-defence and jet-flare test range (IDEA-26 B1/B2, PxFlareDispenser): starts a skirmish on Agenda with a ready scene.
#   You (USA, west spawn): Radar Dome, AA Gun, Medium SAM, Long-range SAM, Missile Shield, an Airfield.
#   Bot (east): Kasirga-X, Fatah-X, Guajiro Grad, Fajir-5 and a V2 launcher in range of your defences, so their
#   rockets fly into your air defence; behind them its own Medium SAM, Long-range SAM and Radar Dome (with power
#   plants: the unlimited-power cheat is yours only), so jets you build at the Airfield and send at the launchers get
#   shot at and drop flares. Two bot F-16s also start in the air over your base: your SAMs fire, they drop flares.
#   North of your base two of your F-16s and a bot Su-27 and MiG-23 start in the air and dogfight (real missile models).
# Test cheats (map revealed, instant build, unlimited power) come from launch-game-test.sh.
#
#   sh tools/test-airdefence.sh          (from the repo root)
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
[ -f "${SKIRMISH}" ] && cp "${SKIRMISH}" "${SKIRMISH}.before-airdef"
[ -f "${SETTINGS}" ] && cp "${SETTINGS}" "${SETTINGS}.before-airdef"
restore() {
	if [ -f "${SKIRMISH}.before-airdef" ]; then mv "${SKIRMISH}.before-airdef" "${SKIRMISH}"; else rm -f "${SKIRMISH}"; fi
	if [ -f "${SETTINGS}.before-airdef" ]; then mv "${SETTINGS}.before-airdef" "${SETTINGS}"; fi
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

# Positions are relative to your start (36,48); @1 = the bot
OURS="dome@+3,-6;agun@+7,-3;msam@+7,+1;lsam@+3,+4;bmd@-2,+6;afld@-7,-5"
THEIRS="kasirga@+18,0@1;fatah@+18,+3@1;grad@+17,-3@1;fajir5@+19,-6@1;v2rl@+16,+6@1"
THEIR_AD="msam@+26,-2@1;lsam@+27,+3@1;dome@+30,0@1;apwr@+32,-5@1;apwr@+32,+4@1;apwr@+35,0@1"
# x,y,health,facing,altitude: jets already flying
THEIR_JETS="jet.f16@+5,-1,100,256,2048@1;jet.f16@+4,+3,100,256,2048@1"
# Dogfight with the real missile models: your F-16s (AIM-9 / AIM-120) against a Su-27 (R-73 / R-77) and a MiG-23
# (R-73 / R-27T), all already flying north of your base
DOGFIGHT="jet.f16@+8,-12,100,768,2048;jet.f16@+8,-9,100,768,2048;jet.su27@+16,-11,100,256,2048@1;jet.mig23@+16,-8,100,256,2048@1"
export RAPX_SPAWN="${OURS};${THEIRS};${THEIR_AD};${THEIR_JETS};${DOGFIGHT}"

sh "${ROOT}/launch-game-test.sh" --start
