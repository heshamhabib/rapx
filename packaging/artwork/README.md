# Application artwork

`icon_*.png` is the application icon at every size the three packaging paths need. It is the "X" from the
Red Alert Project X logo (`mods/rapx/uibits/menu-fx/logo.png`), cropped square and scaled down, so the
game wears its own mark in Explorer, the taskbar and the alt-tab list rather than the mod SDK's "Ex"
placeholder it shipped with.

Regenerate the whole set from the logo if the branding changes, keeping the sizes that are here. The
sizes up to 48px are what the Windows shell actually shows most of the time, so check those first.

`rapx.ico` is generated, not committed: `make.ps1 all` rebuilds it with `tools/make-ico.ps1` whenever it
is missing or older than these PNGs, and the Linux and macOS packaging builds their own with ImageMagick.

`macos-background*.png` is the disk image backdrop, unrelated to the icon.
