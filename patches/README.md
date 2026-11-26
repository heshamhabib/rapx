# Engine patches

`engine/` is OpenRA `release-20250330` with these patches already applied, so you do not need to apply them to
build the game. They are kept as a readable record of every RAPX change to the engine, and for moving to a
newer OpenRA release.

Removed from the engine copy (2026-11-07, IDEA-31): the `all`, `cnc`, `d2k`, `ra` and `ts` game folders and their
`-content` installers, which hold original Westwood/EA art and sounds and are never loaded by RAPX (its `$rapx: ra`
alias makes `ra|` paths point at mods/rapx). Their C# code
(`OpenRA.Mods.Cnc` etc.) is still built. The engine's own `make test`/`make install` targets still name them.

Apply order (`hd-rendering` and `perf-smooth-motion` touch the same code, so order matters):

```
engine-hd-rendering.patch
engine-perf-smooth-motion.patch
engine-airfield-slots.patch
engine-heli-no-airfield-home.patch
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
engine-optional-extras-buttons.patch
engine-nuke-descent.patch
engine-intel-uhd-debug-callback.patch
engine-radar-resize.patch
engine-launcher-extra-args.patch
engine-sprite-downscale.patch
engine-effects-settings.patch
engine-map-preview-scale.patch
engine-smooth-screen-shake.patch
engine-faster-sprite-loading.patch
engine-gpu-memory-and-fill.patch
engine-graphics-card-info.patch
```

## Upgrading the engine

1. Set `ENGINE_VERSION` in `mod.config` to the new release tag and, temporarily,
   `AUTOMATIC_ENGINE_MANAGEMENT="True"`. Delete `engine/` and run `make`: the SDK downloads the stock release
   and prepares it (version stamp, lint cleanup).
2. From inside `engine/`, apply each patch in the order above: `patch -p1 < ../patches/<name>.patch`,
   and resolve any conflicts.
3. Set `AUTOMATIC_ENGINE_MANAGEMENT="False"` again, run `make`, and test.
4. Regenerate any patch you had to change so this folder stays in sync with `engine/`.
