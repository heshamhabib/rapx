#!/bin/sh
# Runs the remaining soldiers through make_soldier.sh one after another (throttled renders, ~1.5-2 h each).
cd "$(dirname "$0")/../../.." || exit 1
run() { echo "===== $1 ($(date +%H:%M))"; sh artsrc/units/soldiers/make_soldier.sh "$1" "$2" > artsrc/units/soldiers/render/$1-chain.log 2>&1; tail -1 artsrc/units/soldiers/render/$1-chain.log; }
run e4   "same fire-resistant suit, helmet, fuel tanks on the back and gear"
run e6   "same hard hat, utility vest, tool bag and gear"
run e7   "same tactical outfit, hair and gear"
run medi "same uniform, helmet and medical backpack with the red cross on white"
run mech "same overalls, cap and tool belt"
run shok "same heavy armour and backpack Tesla unit with its blue glow"
run spy  "same dark suit and trench coat"
echo "===== all done ($(date +%H:%M))"
