#!/bin/bash
# Performance benchmark: ./tools/perf-bench.sh LABEL SECONDS [ENV=VALUE...]   (extra launch args via LAUNCH_ARGS)
# Example: ./tools/perf-bench.sh base 40 RAPX_MENU_SCRIPT="1500:stopvideo;4000:click SINGLEPLAYER_BUTTON;8000:click SKIRMISH_BUTTON;14000:click START_GAME_BUTTON"
# Prints mean FPS, logic tick length (40 = full speed at normal), render timings (PxPerfLog) and CPU/GPU %. settings.yaml is restored.
cd /Users/heshamhabib/code/redalert/RedAlertProjectX
export PATH="$HOME/.dotnet:$PATH" DOTNET_ROOT="$HOME/.dotnet"
SUP="$HOME/Library/Application Support/OpenRA"
LABEL=$1; SECS=$2; shift 2
OUT=${BENCH_OUT:-/tmp}/bench-$LABEL.txt
cp "$SUP/settings.yaml" "$SUP/settings.yaml.bench-bak"
env RAPX_PERFLOG=1 "$@" ./launch-game.sh ${LAUNCH_ARGS} > /dev/null 2>&1 & PID=$!
sleep ${WAIT:-45}
: > "$OUT"
for i in $(seq 1 $((SECS/2))); do
  P=$(pgrep -f "bin/OpenRA.dll" | head -1)
  CPU=$(ps -o %cpu= -p $P 2>/dev/null)
  GPU=$(ioreg -r -d 1 -c IOAccelerator | grep -o '"Device Utilization %"=[0-9]*' | head -1 | cut -d= -f2)
  echo "cpu=$CPU gpu=$GPU" >> "$OUT"; sleep 2
done
pkill -f "bin/OpenRA.dll"; kill $PID 2>/dev/null
for i in $(seq 1 30); do pgrep -f "bin/OpenRA.dll" >/dev/null || break; sleep 1; done; sleep 1
mv "$SUP/settings.yaml.bench-bak" "$SUP/settings.yaml"
grep PxPerfLog "$SUP/Logs/perf.log" | tail -n $((SECS/2)) >> "$OUT"
python3 - "$OUT" <<'PY'
import sys,re,statistics as st
L=open(sys.argv[1]).read().splitlines()
cpu=[float(m.group(1)) for l in L if (m:=re.match(r'cpu=\s*([\d.]+)',l))]
gpu=[float(m.group(1)) for l in L if (m:=re.search(r'gpu=([\d.]+)',l))]
perf=[dict(re.findall(r'(\w+)=([\d.]+)',l)) for l in L if 'PxPerfLog' in l]
def a(k): v=[float(p[k]) for p in perf if k in p]; return round(st.mean(v),2) if v else None
print(sys.argv[1].split('/')[-1], 'cpu%',round(st.mean(cpu),1) if cpu else None,'gpu%',round(st.mean(gpu),1) if gpu else None,
 {k:a(k) for k in ['fps','tickms','render','render_prepare','render_world','render_widgets','render_flip','tick_time','tick_actors','batches','actors']})
PY
