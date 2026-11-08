#!/bin/sh
# Cut a RedAlert Project X release: bump the version in mods/rapx/mod.yaml, turn the
# "Unreleased" section of CHANGELOG.md into a dated release section, commit and tag vX.Y.Z.
#
# Usage:
#   tools/release.sh patch|minor|major [CHANNEL]   bump from the current version
#   tools/release.sh 1.2.0[-channel]               set an exact version
#   tools/release.sh --show                        print the current version
#
# CHANNEL is the pre-release tag shown on the main menu pill (pilot, beta, rc...); "release"
# or "stable" drops it. Without CHANNEL the current channel is kept.
# Nothing is pushed: the script prints the push command at the end.
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="${ROOT}/mods/rapx/mod.yaml"
CHANGELOG="${ROOT}/CHANGELOG.md"

current=$(awk '/^\tVersion:/ { print $2; exit }' "${MANIFEST}")
core=${current%%-*}
channel=""
case "${current}" in *-*) channel=${current#*-} ;; esac

if [ "$1" = "--show" ] || [ -z "$1" ]; then
	echo "${current}"
	[ -z "$1" ] && echo "Usage: $0 patch|minor|major [CHANNEL] | X.Y.Z[-channel] | --show" >&2
	exit 0
fi

major=$(echo "${core}" | cut -d. -f1)
minor=$(echo "${core}" | cut -d. -f2)
patch=$(echo "${core}" | cut -d. -f3)

case "$1" in
	major) next="$((major + 1)).0.0" ;;
	minor) next="${major}.$((minor + 1)).0" ;;
	patch) next="${major}.${minor}.$((patch + 1))" ;;
	[0-9]*.[0-9]*.[0-9]*) next="${1%%-*}"; case "$1" in *-*) channel=${1#*-} ;; *) channel="" ;; esac ;;
	*) echo "Unknown bump '$1' (use patch, minor, major or X.Y.Z)" >&2; exit 1 ;;
esac

[ -n "$2" ] && channel="$2"
case "${channel}" in release|stable) channel="" ;; esac
version="${next}${channel:+-${channel}}"

cd "${ROOT}"
if git rev-parse -q --verify "refs/tags/v${version}" >/dev/null; then
	echo "Tag v${version} already exists." >&2
	exit 1
fi

if ! awk '/^## \[Unreleased\]/ { f = 1; next } /^## / { f = 0 } f && /^[-*] / { n++ } END { exit !n }' "${CHANGELOG}"; then
	echo "CHANGELOG.md has no entries under '## [Unreleased]'. Add what changed first." >&2
	exit 1
fi

# mod.yaml: Version line and the per-version user maps folder (same rule the packaging scripts use).
. "${ROOT}/engine/packaging/functions.sh"
set_mod_version "${version}" "${MANIFEST}"

# CHANGELOG.md: keep an empty Unreleased section on top, date the old one.
today=$(date +%Y-%m-%d)
awk -v v="${version}" -v d="${today}" '
	/^## \[Unreleased\]/ { print; print ""; print "## [" v "] - " d; next }
	{ print }' "${CHANGELOG}" > "${CHANGELOG}.tmp"
mv "${CHANGELOG}.tmp" "${CHANGELOG}"

git add "${MANIFEST}" "${CHANGELOG}"
git commit -q -m "Release ${version}"
git tag -a "v${version}" -m "RedAlert Project X ${version}"

echo "Released ${current} -> ${version} (commit $(git rev-parse --short HEAD), tag v${version})."
echo "Push with: git push origin main --follow-tags"
