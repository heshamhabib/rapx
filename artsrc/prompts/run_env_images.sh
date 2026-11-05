#!/bin/sh
# Map-environment images via ChatGPT: mandatory groups first (materials, trees, props, smudges,
# walls, tech), then civilian buildings and tiles, several items per image (env-sheets.md, cut apart
# by slice_sheet.py). Stops at the first ChatGPT usage limit.
# Progress: assets/env/progress.json + assets/env/PROGRESS.md. Just rerun this to continue:
# saved images are skipped and failed ones are retried.
# Afterwards the new renders are imported into the mod (artsrc/env/make_env.py + make_materials.py).
cd "$(dirname "$0")" || exit 1
caffeinate -i python3 generate_images.py --prompts env-sheets.md --category env \
    --order mandatory --stop-on-limit --track ../../assets/env/progress.json "$@"
status=$?
python3 ../env/make_env.py && python3 ../env/make_materials.py
exit $status
