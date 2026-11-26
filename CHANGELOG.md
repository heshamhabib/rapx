# Changelog

All notable changes to RedAlert Project X. Versions follow [Semantic Versioning](https://semver.org):
`MAJOR.MINOR.PATCH-channel`, where the channel (`pilot`, `beta`, `rc`) marks a pre-release and is shown
on the main menu next to the version number.

- **PATCH** (0.1.0 -> 0.1.1): bug fixes and balance tweaks.
- **MINOR** (0.1.0 -> 0.2.0): new units, weapons, nations, maps or features.
- **MAJOR** (0.x -> 1.0.0): the first full release, then big reworks that break saves, replays or maps.

Add a line under **Unreleased** as you change things, then cut a release with `tools/release.sh`
(see CONTRIBUTING.md). Saves, replays and user maps are kept per version, so players of different
versions cannot play multiplayer together.

## [Unreleased]

- Titans: each player can pick a giant in the lobby's new TITAN column, Godzilla or King Kong (or a surprise pick).
  It walks out beside their start and can never be rebuilt once it falls. Godzilla breathes an atomic beam that also
  hits aircraft, stomps what is at his feet and swims through rivers and the sea (1,000,000 HP); King Kong hammers
  the ground, hurls boulders and leaps to swat jets and helicopters out of the sky (850,000 HP). Both step on enemy
  vehicles and ships in their way, heal slowly out of combat and have their own roars and footsteps.
- Faster game start: the boot load is about 45% shorter (PNG art decodes with vectorised filters and native zlib,
  and pixel conversion moved off the main thread). The art looks exactly the same.
- Smoother play with the same picture: the full-screen effects (HD terrain, cloud shadows, weather, fog of war) no
  longer draw the parts of the world hidden under the sidebar and bottom panel, and the fog of war skips settled
  visible ground, where it changes nothing. A test base at 2940x1846 went from 53 fps to the 60 fps cap.
- Less video memory: filmed effects and landmark flags are trimmed to their visible pixels when the game loads, and
  HD art is packed into larger sheets that waste less space; a match also leaves out the art of nations nobody is
  playing (other nations' units, jets, carriers and building styles), which loads the moment anything needs it.
  A USA vs Russia skirmish uses about 5.8 GB of GPU memory instead of 8.6 GB, with the same art on screen.
- The game reaches the main menu in under 2 seconds instead of about 12: the menu loads no unit art up front, and
  fills it in the background while you are in the menu and the lobby (the nations you pick come next), so a skirmish
  still starts in under a second. Art is also copied into its sheets on several threads, shrunk only where it has
  visible pixels, and converted in place.
- The HD terrain is not re-shaded while the camera holds still: its last result is redrawn (water and anything that
  changes are still drawn fresh), which takes a large part of the GPU work off quiet moments. Checked pixel for pixel.
- Explosions play at real-life speed: the filmed fireballs were slow motion; they now flash and burn out about three
  times faster and their smoke drifts off at a natural pace. Nuclear mushrooms keep their slow rise.
- Settings > Display shows the graphics card the game is drawing on, with its driver version and the other cards in
  the PC, and warns when the game runs on power-saving graphics, without a graphics driver, or with a card whose
  driver is missing. The card is also written to graphics.log and to crash reports.
- Laptops with two graphics cards: on Windows the game now asks for the high-performance card the first time it
  starts (the same choice as Windows Settings > System > Display > Graphics), and a new Graphics Card option in
  Settings > Display switches between High performance, Power saving and Let Windows decide. If the graphics fail to
  start, the error window now names the cards Windows found and what to try.

## [0.1.0-pilot] - 2026-11-08

First pilot build for testers.

- 16 nations on two sides, Union and Vanguard, with national units and building styles.
- HD 3D-rendered units, buildings and effects.
- A real air force: airfields with parking slots, rearming jets, flares and layered air defence.
- Battle robots, superweapons including the USA Fatman Strike, and an in-game Catalogue of every unit.
- Living weather (thunderstorms, rain, snow, blizzards, sandstorms, fog, wind) with a sidebar forecast.
- New maps including Berlin, Archipelago, Desert Rats and Ironward.
- Reskinned menus, lobby and sidebar, a battle report, observer stats and RA2-style controls.
- Cinematic intro trailer and a custom soundtrack.
- Version badge on the main menu.
