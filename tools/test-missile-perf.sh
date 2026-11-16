#!/bin/sh
# Missile salvo frame-rate benchmark: starts a skirmish on Berlin 1946 (the HD city map) with 8 Hailfire trucks
# (30 rockets each) and 6 Thunderhead MLRS (19 each) firing repeated salvos at a group of enemy heavy tanks,
# camera on the launchers, and logs fps / tick / render timings (PxPerfLog, every 50 ticks) plus the live
# particle count to perf.log. The intro video is stopped first so it does not distort the baseline.
#
#   sh tools/test-missile-perf.sh LABEL     (from the repo root; results in /tmp/missile-bench-LABEL.txt)
#   RAPX_PARTICLE_LEGACY=1 sh tools/test-missile-perf.sh legacy   (old per-particle render path, for A/B)
#
# Your saved skirmish lobby and settings.yaml are backed up and restored when the game closes.
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SUPPORT_DIR="${HOME}/Library/Application Support/OpenRA"
SKIRMISH="${SUPPORT_DIR}/skirmish.rapx.yaml"
SETTINGS="${SUPPORT_DIR}/settings.yaml"
BERLIN=d706fd3af53d79f07b02bf00cd34bd4a3230c818
LABEL=${1:-run}
OUT="/tmp/missile-bench-${LABEL}.txt"

if pgrep -f "bin/OpenRA.dll" > /dev/null; then
	echo "OpenRA is already running - not starting a second instance" >&2
	exit 1
fi

mkdir -p "${SUPPORT_DIR}"
[ -f "${SKIRMISH}" ] && cp "${SKIRMISH}" "${SKIRMISH}.before-mperf"
[ -f "${SETTINGS}" ] && cp "${SETTINGS}" "${SETTINGS}.before-mperf"
restore() {
	if [ -f "${SKIRMISH}.before-mperf" ]; then mv "${SKIRMISH}.before-mperf" "${SKIRMISH}"; else rm -f "${SKIRMISH}"; fi
	if [ -f "${SETTINGS}.before-mperf" ]; then mv "${SETTINGS}.before-mperf" "${SETTINGS}"; fi
}
trap restore EXIT INT TERM

# Berlin 1946, you on spawn 1 (15,28), one easy bot on spawn 4 (116,70), far away
python3 - "${SKIRMISH}" "${BERLIN}" <<'PYEOF'
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
    "Bots:", "\teasy: Multi1", "\t\tColor: F25FA0", "\t\tFaction: turkey", "\t\tSpawnPoint: 4", "\t\tTeam: 0",
    "\t\tHandicap: 0"]
open(path, "w").write("\n".join(out) + "\n")
PYEOF

# Two rows of launchers east of spawn 1 (15,28); a pack of enemy heavy tanks ~12 cells further east as a big
# tanky target the salvos keep pounding (owner @1 = the bot). Vehicles spawn on any clear city ground.
LAUNCHERS="hlfr@+4,+0;hlfr@+5,+0;hlfr@+6,+0;hlfr@+7,+0;hlfr@+4,+2;hlfr@+5,+2;hlfr@+6,+2;hlfr@+7,+2"
MLRS="mlrs@+4,+4;mlrs@+5,+4;mlrs@+6,+4;mlrs@+7,+4;mlrs@+4,+6;mlrs@+5,+6"
TARGETS="4tnk@+16,+0@1;4tnk@+17,+2@1;4tnk@+16,+4@1;4tnk@+17,+6@1;4tnk@+16,+2@1;4tnk@+17,+0@1;4tnk@+16,+6@1;4tnk@+17,+4@1;4tnk@+18,+1@1;4tnk@+18,+5@1"
export RAPX_SPAWN="${LAUNCHERS};${MLRS};${TARGETS}"

# World is loaded by ~35 s; stop the intro video first (it would otherwise decode 1080p frames behind the whole
# run). Watch the launchers (the salvo and its trails fill the screen like the user's shot), fire at 42 s and
# keep re-ordering every reload; quit after ~100 s of sustained salvos.
export RAPX_TEST_EXTRA="25000:stopvideo;40000:focus hlfr 1;42000:attack hlfr,mlrs 4tnk;45000:shot;48000:shot;52000:shot;60000:attack hlfr,mlrs 4tnk;64000:shot;78000:attack hlfr,mlrs 4tnk;96000:attack hlfr,mlrs 4tnk;114000:attack hlfr,mlrs 4tnk;140000:quit"

: > "${OUT}"
RAPX_PERFLOG=1 sh "${ROOT}/launch-game-test.sh" --start > /dev/null 2>&1 &
GAME=$!

# Sample CPU/GPU while it runs (GPU from IOAccelerator device utilization)
for i in $(seq 1 70); do
	P=$(pgrep -f "bin/OpenRA.dll" | head -1)
	[ -z "${P}" ] && { sleep 2; continue; }
	CPU=$(ps -o %cpu= -p "${P}" 2>/dev/null || true)
	GPU=$(ioreg -r -d 1 -c IOAccelerator | grep -o '"Device Utilization %"=[0-9]*' | head -1 | cut -d= -f2)
	echo "cpu=${CPU} gpu=${GPU}" >> "${OUT}"
	sleep 2
done

wait ${GAME} 2>/dev/null || true
grep PxPerfLog "${SUPPORT_DIR}/Logs/perf.log" >> "${OUT}"
echo "results in ${OUT}"
