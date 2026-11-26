#!/bin/sh
# Load-time, frame-rate and memory benchmark in one run (IDEA-27):
#
#   sh tools/perf-suite.sh LABEL [SECONDS]        results in ${BENCH_OUT:-/tmp}/suite-LABEL/
#
# Boots the game (intro skipped), starts a skirmish on Great Sahara 2 (you: USA, one normal bot: Russia, clear
# weather pinned), deploys the MCV, spawns a small base and army next to it, watches it for SECONDS (default 60) with
# VSync off, then quits. While it runs it samples the game's memory footprint (all of it and the GPU part) and the
# GPU's busy % and memory in use. Prints boot and skirmish load times, frame rate and render timings (PxPerfLog),
# sprite sheet counts and memory, and keeps perf.log, debug.log and the per-file sprite report (sprite-report.tsv)
# next to the summary.
#
# Your settings.yaml and saved skirmish lobby are backed up and restored when the game closes. Extra environment
# variables (e.g. RAPX_PARTICLE_LEGACY=1) pass through to the game.
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SUP="${HOME}/Library/Application Support/OpenRA"
SKIRMISH="${SUP}/skirmish.rapx.yaml"
SETTINGS="${SUP}/settings.yaml"
LABEL=${1:?usage: perf-suite.sh LABEL [SECONDS]}
SECS=${2:-60}
OUT="${BENCH_OUT:-/tmp}/suite-${LABEL}"
SAHARA=$(python3 "${ROOT}/tools/map_uid.py" "${ROOT}/mods/rapx/maps/great-sahara-2.oramap")

# The game process only: a shell whose command line merely mentions the dll must not match
gamepid() { pgrep -f '^dotnet bin/OpenRA\.dll' | head -1; }

if [ -n "$(gamepid)" ]; then
	echo "OpenRA is already running - not starting a second instance" >&2
	exit 1
fi

mkdir -p "${OUT}"
rm -f "${OUT}"/*
[ -f "${SKIRMISH}" ] && cp "${SKIRMISH}" "${SKIRMISH}.before-suite"
[ -f "${SETTINGS}" ] && cp "${SETTINGS}" "${SETTINGS}.before-suite"
restore() {
	if [ -f "${SKIRMISH}.before-suite" ]; then mv "${SKIRMISH}.before-suite" "${SKIRMISH}"; else rm -f "${SKIRMISH}"; fi
	if [ -f "${SETTINGS}.before-suite" ]; then mv "${SETTINGS}.before-suite" "${SETTINGS}"; fi
}
trap restore EXIT INT TERM

python3 - "${SKIRMISH}" "${SAHARA}" <<'PYEOF'
import sys
path, uid = sys.argv[1], sys.argv[2]
options = {"explored": "False", "fog": "True", "startingcash": "10000", "cheats": "True", "crates": "False",
    "weather": "visual", "weatherchanges": "off", "buildradius": "True", "shortgame": "True", "techlevel": "unrestricted",
    "gamespeed": "default", "startingunits": "none", "peacetreaty": "0", "timelimit": "0"}
out = ["Map: " + uid, "Options:"] + ["\t%s: %s" % kv for kv in options.items()] + [
    "Player: Multi0", "\tColor: 1E3CD2", "\tFaction: usa", "\tSpawnPoint: 1", "\tTeam: 0", "\tHandicap: 0",
    "Bots:", "\tnormal: Multi1", "\t\tColor: E02424", "\t\tFaction: russia", "\t\tSpawnPoint: 2", "\t\tTeam: 0",
    "\t\tHandicap: 0"]
open(path, "w").write("\n".join(out) + "\n")
PYEOF

# A small base and army east of the start (buildings run their smoke/light effects, units idle), plus jets parked
BASE="powr@+4,-3;powr@+7,-3;tent@+4,+1;weap@+8,+1;proc@+4,+5;dome@+9,+5;gun@+12,-1;agun@+12,+3"
ARMY="2tnk@+2,+8;2tnk@+3,+8;2tnk@+4,+8;1tnk@+5,+8;jeep@+6,+8;apc@+7,+8;arty@+8,+8;harv@+9,+8"
INF="e1@+2,+10;e1@+3,+10;e1@+4,+10;e3@+5,+10;e3@+6,+10;e6@+7,+10;medi@+8,+10;dog@+9,+10"
export RAPX_SPAWN="${BASE};${ARMY};${INF}"
export RAPX_WEATHER=Clear RAPX_WEATHER_TICKS=1000000
QUIT=$((52000 + SECS * 1000))
export RAPX_MENU_SCRIPT="1500:stopvideo;5000:click SINGLEPLAYER_BUTTON;14000:click SKIRMISH_BUTTON;20000:click START_GAME_BUTTON;36000:select mcv;37000:key F;40000:focus 2tnk 1;${QUIT}:quit"

export PATH="${HOME}/.dotnet:${PATH}" DOTNET_ROOT="${HOME}/.dotnet"
T0=$(python3 -c 'import time; print(time.time())')
RAPX_PERFLOG=1 RAPX_SPRITE_REPORT=1 "${ROOT}/launch-game.sh" Graphics.VSync=False > /dev/null 2>&1 &
GAME=$!

# Sample every 2 s until the game exits (or a generous timeout)
: > "${OUT}/samples.txt"
LIMIT=$(( (QUIT / 1000) + 120 ))
i=0
while kill -0 "${GAME}" 2>/dev/null && [ ${i} -lt ${LIMIT} ]; do
	P=$(gamepid)
	T=$(python3 -c "import time; print(round(time.time() - ${T0}, 1))")
	STATS=$(ioreg -r -d 1 -c IOAccelerator | grep -o '"PerformanceStatistics" = {[^}]*}' | head -1)
	GPU=$(echo "${STATS}" | grep -o '"Device Utilization %"=[0-9]*' | cut -d= -f2)
	GMEM=$(echo "${STATS}" | grep -o '"In use system memory"=[0-9]*' | cut -d= -f2)
	if [ -n "${P}" ] && [ $((i % 5)) -eq 0 ]; then
		FP=$(footprint -p "${P}" 2>/dev/null | awk '/Footprint:/ {print $(NF-5), $(NF-4)} /IOAccelerator \(graphics\)$/ {print "gfx", $1, $2} /\(unmapped\) \(graphics\)$/ {print "gfxu", $1, $2}' | tr '\n' ' ')
	else
		FP=""
	fi
	CPU=$( [ -n "${P}" ] && ps -o %cpu= -p "${P}" 2>/dev/null || true)
	echo "t=${T} cpu=${CPU} gpu=${GPU} gpumem=${GMEM} fp=${FP}" >> "${OUT}/samples.txt"
	i=$((i + 2))
	sleep 2
done
P=$(gamepid)
[ -n "${P}" ] && kill "${P}" 2>/dev/null || true
for i in $(seq 1 30); do [ -n "$(gamepid)" ] || break; sleep 1; done
sleep 1

cp "${SUP}/Logs/perf.log" "${SUP}/Logs/debug.log" "${OUT}/" 2>/dev/null || true
cp "${SUP}/Logs/sprite-report.tsv" "${OUT}/" 2>/dev/null || true
python3 "${ROOT}/tools/perf-suite-summary.py" "${OUT}" | tee "${OUT}/summary.txt"
