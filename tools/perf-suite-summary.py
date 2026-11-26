#!/usr/bin/env python3
"""Summarises a tools/perf-suite.sh run directory: load times, frame rate, render timings, memory and GPU use.

  python3 tools/perf-suite-summary.py /tmp/suite-LABEL
"""
import os
import re
import statistics as st
import sys

out = sys.argv[1]


def read(name):
    path = os.path.join(out, name)
    return open(path, errors="replace").read().splitlines() if os.path.exists(path) else []


def mean(values):
    return round(st.mean(values), 2) if values else None


def to_mb(value, unit):
    return float(value) * {"B": 1 / 1048576, "KB": 1 / 1024, "MB": 1, "GB": 1024}.get(unit, 1)


debug, perf, samples = read("debug.log"), read("perf.log"), read("samples.txt")

print("== Loads (load screen timer)")
for line in debug:
    m = re.search(r"Load screen: (\w+) load took ([\d.]+)s", line)
    if m:
        print(f"  {m.group(1):5s} {m.group(2):>6s} s")

print("== StartGame totals (perf.log)")
starts = []
for i, line in enumerate(perf):
    if line.strip() == "StartGame":
        for later in perf[i + 1:]:
            m = re.match(r"\s*(\d+) ms -{20,}$", later)
            if m and later.startswith(" ") and len(later) - len(later.lstrip()) <= 6 and later.rstrip().endswith("-" * 50):
                starts.append(int(m.group(1)))
                break
print("  " + ", ".join(f"{s} ms" for s in starts))

for line in perf:
    if line.startswith("SpriteCache: decoded") and " 0 files" not in line:
        print("  " + line)
    if line.startswith("SpriteCache: downscaled") and "0 of 0" not in line:
        print("  " + line)

print("== In game (PxPerfLog, first two samples skipped)")
rows = [dict(re.findall(r"(\w+)=([\d.]+)", l)) for l in perf if "PxPerfLog" in l][2:]
keys = ["fps", "tickms", "render", "render_prepare", "render_world", "render_widgets", "render_flip", "tick_time",
    "tick_actors", "batches", "actors", "particles"]
print("  samples", len(rows))
for k in keys:
    values = [float(r[k]) for r in rows if k in r]
    if values:
        print(f"  {k:15s} mean {mean(values):8.2f}  min {min(values):8.2f}  max {max(values):8.2f}")

print("== Machine samples")
cpu, gpu, gpumem, fp, gfx = [], [], [], [], []
for line in samples:
    d = dict(re.findall(r"(\w+)=([\d.]+)", line))
    if "cpu" in d:
        cpu.append(float(d["cpu"]))
    if "gpu" in d:
        gpu.append(float(d["gpu"]))
    if "gpumem" in d:
        gpumem.append(float(d["gpumem"]) / 1048576)
    m = re.search(r"fp=([\d.]+) (\w+)", line)
    if m:
        fp.append(to_mb(m.group(1), m.group(2)))
    g = re.search(r"gfx ([\d.]+) (\w+)", line)
    gu = re.search(r"gfxu ([\d.]+) (\w+)", line)
    if g or gu:
        gfx.append((to_mb(*g.groups()) if g else 0) + (to_mb(*gu.groups()) if gu else 0))

# The in-game half of the run (after the skirmish has loaded) is what matters for cpu/gpu
half = len(samples) // 2
gpu_late = [float(d["gpu"]) for d in (dict(re.findall(r"(\w+)=([\d.]+)", l)) for l in samples[half:]) if "gpu" in d]
cpu_late = [float(d["cpu"]) for d in (dict(re.findall(r"(\w+)=([\d.]+)", l)) for l in samples[half:]) if "cpu" in d]
print(f"  cpu% (2nd half) {mean(cpu_late)}  gpu% (2nd half) {mean(gpu_late)}")
if gpumem:
    print(f"  GPU memory in use, system-wide: min {min(gpumem):.0f} MB  max {max(gpumem):.0f} MB")
if fp:
    print(f"  game footprint: max {max(fp):.0f} MB  last {fp[-1]:.0f} MB")
if gfx:
    print(f"  game graphics memory (IOAccelerator + unmapped graphics): max {max(gfx):.0f} MB  last {gfx[-1]:.0f} MB")

report = read("sprite-report.tsv")
if report:
    print("== Sprite report (boot load)")
    by_folder = {}
    total_dec = total_packed = 0
    for line in report[1:]:
        f = line.split("\t")
        if len(f) < 4:
            continue
        name, decoded, packed = f[0], int(f[2] or 0), int(f[3] or 0)
        parts = name.split("/")
        folder = "/".join(parts[:4]) if len(parts) > 4 else "/".join(parts[:3])
        d, p, n = by_folder.get(folder, (0, 0, 0))
        by_folder[folder] = (d + decoded, p + packed, n + 1)
        total_dec += decoded
        total_packed += packed
    print(f"  {len(report) - 1} files, decoded {total_dec / 1e6:.0f} MT, packed {total_packed / 1e6:.0f} MT")
    for folder, (d, p, n) in sorted(by_folder.items(), key=lambda kv: -kv[1][1])[:20]:
        print(f"  {p / 1e6:8.1f} MT packed {d / 1e6:8.1f} MT decoded {n:5d} files  {folder}")
