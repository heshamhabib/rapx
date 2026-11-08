# OpenRA Mod SDK Contributing Guidelines

Thank you for your interest in OpenRA, OpenRA modding, and the OpenRA Mod SDK.  OpenRA is an open source project, and our community members – you – are the driving force behind it.  There are many ways to contribute, from writing tutorials or blog posts, improving the documentation, submitting bug reports and feature requests or writing code which can be incorporated into OpenRA, the Mod SDK, or our other sub-projects.

Please note that this repository is specifically for the scripts and infrastructure used to develop and build mods; bugs and feature requests against OpenRA itself should be directed to [the main OpenRA/OpenRA repository](https://github.com/OpenRA/OpenRA).  If you do come across a bug with the Mod SDK, or would like to request a new feature, then please take a look at the issue tracker first to see if it has already been reported.

When developing new features, it is important to make sure that they work on all our supported platforms.  Right now, this means Windows >= 7 (with PowerShell >= 3), macOS >= 10.7, and Linux.  We would like to also support *BSD, but do not currently have a means to test this.

Some issues to be aware of include:
* Use https://www.shellcheck.net/ to confirm POSIX compatibility of *.sh scripts.
* Avoid non-standard gnu extensions to common Unix tools (e.g. the `-f` flag from GNU `readlink`)

While your pull-request is in review it will be helpful if you join IRC to discuss the changes.

See also the in-depth guide on [contributing](https://github.com/OpenRA/OpenRA/wiki/Contributing) on the main OpenRA project wiki.  Most of the content on this page also applies to the Mod SDK.

## Versioning and releases

RedAlert Project X uses [Semantic Versioning](https://semver.org) with a channel suffix, for example
`0.1.0-pilot`. The version lives in `mods/rapx/mod.yaml` (`Metadata: Version:`) and is shown on the main menu.

1. As you change things, add a line under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md).
2. Cut a release with `tools/release.sh`:
   - `tools/release.sh patch` for fixes and balance (0.1.0 -> 0.1.1)
   - `tools/release.sh minor` for new content or features (0.1.0 -> 0.2.0)
   - `tools/release.sh major` for 1.0 and big breaking reworks
   - add a channel to switch it: `tools/release.sh minor beta`, or `release` to drop the suffix
   - `tools/release.sh --show` prints the current version
3. The script updates `mod.yaml`, dates the changelog section, commits and tags `vX.Y.Z`.
   Push with `git push origin main --follow-tags`.
