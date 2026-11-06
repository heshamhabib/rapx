# Engine patches

`engine/` is OpenRA `release-20250330` with these patches already applied, so you do not need to apply them to
build the game. They are kept as a readable record of every RAPX change to the engine, and for moving to a
newer OpenRA release.

Apply order (`hd-rendering` and `perf-smooth-motion` touch the same code, so order matters):

```
engine-hd-rendering.patch
engine-perf-smooth-motion.patch
engine-airfield-slots.patch
engine-carrier-deck.patch
engine-hidpi-cursors.patch
engine-long-cash.patch
engine-music-seek.patch
engine-palette-filter.patch
engine-power-saving.patch
engine-production-tabs.patch
engine-quad-palette-sprite.patch
engine-shared-sprites.patch
engine-text-notification-pools.patch
engine-viewport-clamp.patch
```

## Upgrading the engine

1. Set `ENGINE_VERSION` in `mod.config` to the new release tag and, temporarily,
   `AUTOMATIC_ENGINE_MANAGEMENT="True"`. Delete `engine/` and run `make`: the SDK downloads the stock release
   and prepares it (version stamp, lint cleanup).
2. From inside `engine/`, apply each patch in the order above: `patch -p1 < ../patches/<name>.patch`,
   and resolve any conflicts.
3. Set `AUTOMATIC_ENGINE_MANAGEMENT="False"` again, run `make`, and test.
4. Regenerate any patch you had to change so this folder stays in sync with `engine/`.
