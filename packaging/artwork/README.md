# Application artwork

`icon_*.png` is the application icon at every size the three packaging paths need. It is the red "X" of
the Red Alert Project X logo redrawn as an armoured steel-and-red emblem (generated at 1024x1024 with an
image model, then scaled down with Lanczos), so the game wears its own mark in Explorer, the taskbar and
the alt-tab list rather than the mod SDK's "Ex" placeholder it shipped with.

Regenerate the whole set from `icon_1024x1024.png` if the branding changes, keeping the sizes that are
here. The sizes up to 48px are what the Windows shell actually shows most of the time, so check those
first: the X must fill the frame to stay readable at 16px.

`rapx.ico` is generated, not committed: `make.ps1 all` rebuilds it with `tools/make-ico.ps1` whenever it
is missing or older than these PNGs, and the Linux and macOS packaging builds their own with ImageMagick.

`macos-background*.png` is the disk image backdrop, unrelated to the icon.
