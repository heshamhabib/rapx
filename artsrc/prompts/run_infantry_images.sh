#!/bin/sh
# Infantry animation sheets via ChatGPT (infantry-anim-prompts.md, made by make_infantry_anim_prompts.py).
# Each prompt attaches the soldier's concept image (assets/units/<id>.png) as the character reference.
# Saves to assets/units/<id>/<anim>.png; progress in assets/units/anim-progress.json + PROGRESS.md.
# Rerun to continue: saved sheets are skipped, failed ones retried. Pass --only e1 to do one soldier.
cd "$(dirname "$0")" || exit 1
exec caffeinate -i python3 generate_images.py --prompts infantry-anim-prompts.md --category units \
    --stop-on-limit --track ../../assets/units/anim-progress.json "$@"
