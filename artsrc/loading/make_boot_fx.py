#!/usr/bin/env python3
"""Build the animated light layers for the boot loading screen (mods/rapx/uibits/background.png).

Same layers as the main menu (see artsrc/menu-bg/make_menu_fx.py): the logo glows and pulses, a band of
light sweeps across the chrome letters, fires flicker, lens flares twinkle and embers rise. Drawn by
FullscreenImageLoadScreen through PxMenuFxWidget while the game boots.

Writes mods/rapx/uibits/boot-fx/*.png and boot-fx/boot-fx.yaml. Spots are in background.png pixels;
re-run after replacing background.png, and move the spots if the art changes.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "menu-bg"))

from make_menu_fx import UIBITS, build  # noqa: E402

# name: (cx, cy, rx, ry, mask, effect, speed, min, max), as in make_menu_fx.py
SPOTS = {
    "globe": (835, 340, 420, 320, "red", "Pulse", 0.18, 0.0, 0.35),
    "logo": (835, 450, 540, 240, "red", "Pulse", 0.3, 0.15, 0.75),
    "x-core": (845, 585, 220, 120, "red", "Pulse", 0.55, 0.0, 0.7),
    "logo-shine": (835, 440, 520, 210, "shine", "Shine", 0.22, 0.0, 1.8),
    "fire-left": (130, 640, 230, 140, "fire", "Flicker", 1.0, 0.3, 1.5),
    "fire-ground": (420, 760, 300, 120, "fire", "Flicker", 0.8, 0.2, 1.1),
    "fire-right": (1500, 630, 200, 120, "fire", "Flicker", 1.1, 0.3, 1.6),
    "fire-far-right": (1630, 560, 120, 140, "fire", "Flicker", 0.9, 0.2, 1.3),
    "flare-left": (234, 410, 170, 34, "bright", "Twinkle", 0.5, 0.1, 1.0),
    "flare-right": (1600, 405, 210, 40, "bright", "Twinkle", 0.4, 0.1, 1.0),
}

# Blinking red warning lights: (x, y, size, period seconds, phase)
BEACONS = {
    "heli": (262, 262, 14, 1.2, 0.0),
    "tower": (1648, 372, 12, 1.7, 0.6),
}

# Where embers rise from: x, y, width, height
EMBER_SOURCES = [
    (0, 600, 620, 341),
    (620, 800, 500, 141),
    (1150, 560, 522, 381),
]

# Where distant explosions flash: x, y, width, height
FLASH_AREA = (1220, 470, 440, 200)

if __name__ == "__main__":
    build(os.path.join(UIBITS, "background.png"), os.path.join(UIBITS, "boot-fx"), "ra|uibits/boot-fx",
          SPOTS, BEACONS, EMBER_SOURCES, FLASH_AREA)
