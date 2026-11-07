# RedAlert Project X (RAPX)

A modernised Command & Conquer: Red Alert, built as a mod on the [OpenRA](https://www.openra.net) engine.

- HD art: 3D-rendered units and buildings, national building styles, HD effects and money popups
- Two sides, **Union** and **Vanguard**, with 18 playable nations and their flags
- New buildings (Oil Rig, airfields with parking slots, …), weapons and maps
- Fully reskinned menus, lobby and sidebar, plus a cinematic intro
- RA2-style control schemes

This repository is **self-contained**: the patched OpenRA engine is included in `engine/`, so a single clone is
all you need to build and play.

## Build and play

### Requirements

- [.NET 6 SDK](https://dotnet.microsoft.com/download/dotnet/6.0)
- Linux only: SDL 2, FreeType, OpenAL and Lua 5.1 system libraries
  (e.g. `sudo apt install libfreetype6 libopenal1 liblua5.1-0 libsdl2-2.0-0`; other distros in
  [engine/INSTALL.md](engine/INSTALL.md))

### macOS / Linux

```sh
git clone https://github.com/heshamhabib/rapx.git
cd rapx
make
./launch-game.sh
```

### Windows

```bat
git clone https://github.com/heshamhabib/rapx.git
cd rapx
make.cmd
launch-game.cmd
```

Everything the game needs is in this repository: no Red Alert files are downloaded or installed, and it runs
offline.

## Repository layout

| Path | What it is |
|---|---|
| `OpenRA.Mods.RAPX/` | C# mod code: traits, widgets, projectiles, warheads, video loader, … |
| `mods/rapx/` | The mod itself: rules, weapons, sequences, chrome (UI), HD art (`bits/`), maps, audio |
| `engine/` | OpenRA engine `release-20250330` with the RAPX engine patches already applied |
| `patches/` | The same engine changes as patch files, a record of what differs from stock OpenRA |
| `artsrc/` | Art pipeline: scripts that generate the HD sprites, UI skin, flags, cameos, maps and sounds |
| `tools/` | Helper scripts (video encoder, perf bench, art audit) |
| `docs/` | Campaign story, research notes, asset inventories |
| `packaging/` | Scripts for building Windows / macOS / Linux installers |

Raw source art (Blender scenes, 3D model downloads and intermediate renders, tens of GB) is not part of the
repository; `artsrc/` holds the scripts and the inputs needed to regenerate the shipped art.

## The engine

`engine/` is OpenRA [`release-20250330`](https://github.com/OpenRA/OpenRA/releases/tag/release-20250330) with
the patches in [`patches/`](patches/) applied (HD rendering, 64-bit cash, airfield slots, production tabs,
smooth motion, …). `mod.config` sets `AUTOMATIC_ENGINE_MANAGEMENT="False"`, so `make` builds this copy and
never downloads a stock engine over it. See [patches/README.md](patches/README.md) for upgrading to a newer
OpenRA release.

## License and credits

- RAPX code and data: [GNU AGPL v3](LICENSE).
- The OpenRA engine (`engine/`) and the OpenRA Mod SDK scripts: GNU GPL v3 ([engine/COPYING](engine/COPYING),
  [COPYING](COPYING)). Engine authors are listed in [engine/AUTHORS](engine/AUTHORS).
- Command & Conquer: Red Alert is © Electronic Arts. RAPX contains none of its art, sounds, music or videos: every
  sprite, terrain tile, voice and sound effect is our own or third-party under the licences in
  [mods/rapx/CREDITS](mods/rapx/CREDITS). Terrain tiles and building bibs keep the shapes of the classic templates (where
  grass, cliff and water meet) so existing maps still fit, repainted with our own colours (artsrc/terrain/make_base_tiles.py).
- 3D models, textures and sounds are by their respective authors under Creative Commons and other
  licenses; see [mods/rapx/CREDITS](mods/rapx/CREDITS). A few are licensed **NonCommercial**, so RAPX must not
  be sold.

RAPX is a free fan project and is not affiliated with or endorsed by Electronic Arts or the OpenRA team.
