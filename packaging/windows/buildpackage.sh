#!/bin/bash
set -e
# This script was originally written to cross-build from Linux. It also runs on a
# native Windows shell (MSYS2 / Git Bash), where the Microsoft tooling runs directly
# and wine is therefore not needed. Detect which case we are in.
case "$(uname -s)" in
	MINGW*|MSYS*|CYGWIN*) HOST_WINDOWS="True" ;;
	*) HOST_WINDOWS="False" ;;
esac

if [ "${HOST_WINDOWS}" = "True" ]; then
	# NSIS and ImageMagick install outside the PATH that MSYS2 inherits by default.
	for CANDIDATE in "/c/Program Files (x86)/NSIS" "/c/Program Files/NSIS"; do
		[ -x "${CANDIDATE}/makensis.exe" ] && PATH="${PATH}:${CANDIDATE}"
	done
	for CANDIDATE in "/c/Program Files/ImageMagick-"*; do
		[ -x "${CANDIDATE}/magick.exe" ] && PATH="${PATH}:${CANDIDATE}"
	done
	export PATH
fi

command -v curl >/dev/null 2>&1 || command -v wget > /dev/null 2>&1 || { echo >&2 "The OpenRA mod SDK Windows packaging requires curl or wget."; exit 1; }
command -v makensis >/dev/null 2>&1 || { echo >&2 "The OpenRA mod SDK Windows packaging requires makensis."; exit 1; }

# ImageMagick 7 renamed `convert` to `magick`, and on Windows `convert` is already
# taken by the NTFS conversion tool in System32 -- so `magick` must win where present.
if command -v magick >/dev/null 2>&1; then
	MAGICK="magick"
elif [ "${HOST_WINDOWS}" = "False" ] && command -v convert >/dev/null 2>&1; then
	MAGICK="convert"
else
	echo >&2 "The OpenRA mod SDK Windows packaging requires ImageMagick."
	exit 1
fi

# `python3` on Windows is usually a Microsoft Store alias stub that prints an advert
# and exits without running anything, so probe for one that actually executes.
if python3 -c "" >/dev/null 2>&1; then
	PYTHON="python3"
elif python -c "" >/dev/null 2>&1; then
	PYTHON="python"
else
	echo >&2 "The OpenRA mod SDK Windows packaging requires python 3."
	exit 1
fi

if [ "${HOST_WINDOWS}" = "False" ]; then
	command -v wine64 >/dev/null 2>&1 || { echo >&2 "The OpenRA mod SDK Windows packaging requires wine64."; exit 1; }
	RCEDIT="wine64 rcedit-x64.exe"
else
	# rcedit is a Windows binary, so it runs directly here.
	RCEDIT="./rcedit-x64.exe"
fi

# makensis and ImageMagick are native Windows binaries. Hand them Windows paths
# explicitly rather than relying on the shell to rewrite POSIX ones in passing.
if [ "${HOST_WINDOWS}" = "True" ]; then
	topath() { cygpath -m "${1}"; }
else
	topath() { printf '%s\n' "${1}"; }
fi

# Win32 COLORREF values are 0x00BBGGRR -- the reverse byte order of the RRGGBB used
# in mod.config, so the progress bar colours have to be swapped on the way through.
to_bgr() { printf '0x%s%s%s' "${1:4:2}" "${1:2:2}" "${1:0:2}"; }

require_variables() {
	missing=""
	for i in "$@"; do
		eval check="\$$i"
		[ -z "${check}" ] && missing="${missing}   ${i}\n"
	done
	if [ -n "${missing}" ]; then
		printf "Required mod.config variables are missing:\n%sRepair your mod.config (or user.config) and try again.\n" "${missing}"
		exit 1
	fi
}

if [ $# -eq "0" ]; then
	echo "Usage: $(basename "$0") version [outputdir]"
	exit 1
fi

PACKAGING_DIR=$(${PYTHON} -c "import os; print(os.path.dirname(os.path.realpath('$0')))")

# engine/packaging/functions.sh invokes `python3` directly. Shim it onto PATH when the
# real interpreter goes by another name, rather than patching the engine checkout.
if [ "${PYTHON}" != "python3" ]; then
	SHIM_DIR="${PACKAGING_DIR}/.shim"
	mkdir -p "${SHIM_DIR}"
	cat > "${SHIM_DIR}/python3" <<-SHIM
		#!/bin/sh
		exec ${PYTHON} "\$@"
	SHIM
	chmod +x "${SHIM_DIR}/python3"
	PATH="${SHIM_DIR}:${PATH}"
	export PATH
fi
TEMPLATE_ROOT="${PACKAGING_DIR}/../../"
ARTWORK_DIR="${PACKAGING_DIR}/../artwork/"

# shellcheck source=mod.config
. "${TEMPLATE_ROOT}/mod.config"

if [ -f "${TEMPLATE_ROOT}/user.config" ]; then
	# shellcheck source=user.config
	. "${TEMPLATE_ROOT}/user.config"
fi

require_variables "MOD_ID" "ENGINE_DIRECTORY" "PACKAGING_DISPLAY_NAME" "PACKAGING_INSTALLER_NAME" "PACKAGING_COPY_CNC_DLL" "PACKAGING_COPY_D2K_DLL" \
	"PACKAGING_WINDOWS_LAUNCHER_NAME" "PACKAGING_WINDOWS_REGISTRY_KEY" "PACKAGING_WINDOWS_INSTALL_DIR_NAME" \
	"PACKAGING_WINDOWS_LICENSE_FILE" "PACKAGING_FAQ_URL" "PACKAGING_WEBSITE_URL" "PACKAGING_AUTHORS" "PACKAGING_OVERWRITE_MOD_VERSION" \
	"PACKAGING_WINDOWS_PLATFORMS" "PACKAGING_WINDOWS_THEME_ART" "PACKAGING_WINDOWS_THEME_LOGO_CROP" "PACKAGING_WINDOWS_THEME_BACKDROP_CROP" \
	"PACKAGING_WINDOWS_THEME_FONT" "PACKAGING_WINDOWS_THEME_BG" "PACKAGING_WINDOWS_THEME_TEXT" "PACKAGING_WINDOWS_THEME_ACCENT"

TAG="$1"
if [ $# -eq "1" ]; then
	OUTPUTDIR=$(${PYTHON} -c "import os; print(os.path.realpath('.'))")
else
	OUTPUTDIR=$(${PYTHON} -c "import os; print(os.path.realpath('$2'))")
fi

BUILTDIR="${PACKAGING_DIR}/build"
THEME_DIR="${PACKAGING_DIR}/theme"

# Set the working dir to the location of this script
cd "${PACKAGING_DIR}"

if [ ! -f "${TEMPLATE_ROOT}/${ENGINE_DIRECTORY}/Makefile" ]; then
	echo "Required engine files not found."
	echo "Run \`make\` in the mod directory to fetch and build the required files, then try again.";
	exit 1
fi

. "${TEMPLATE_ROOT}/${ENGINE_DIRECTORY}/packaging/functions.sh"
. "${TEMPLATE_ROOT}/packaging/functions.sh"

if [ ! -d "${OUTPUTDIR}" ]; then
	echo "Output directory '${OUTPUTDIR}' does not exist.";
	exit 1
fi

if command -v curl >/dev/null 2>&1; then
	curl -s -L -O https://github.com/electron/rcedit/releases/download/v1.1.1/rcedit-x64.exe || exit 3
else
	wget -cq https://github.com/electron/rcedit/releases/download/v1.1.1/rcedit-x64.exe || exit 3
fi

function build_platform()
{
	PLATFORM="${1}"
	if [ "${PLATFORM}" = "x86" ]; then
		USE_PROGRAMFILES32="-DUSE_PROGRAMFILES32=true"
	else
		USE_PROGRAMFILES32=""
	fi

	if [ -n "${PACKAGING_DISCORD_APPID}" ]; then
		USE_DISCORDID="-DUSE_DISCORDID=${PACKAGING_DISCORD_APPID}"
	else
		USE_DISCORDID=""
	fi

	echo "Building core files (${PLATFORM})"
	install_assemblies "${TEMPLATE_ROOT}/${ENGINE_DIRECTORY}" "${BUILTDIR}" "win-${PLATFORM}" "net6" "False" "${PACKAGING_COPY_CNC_DLL}" "${PACKAGING_COPY_D2K_DLL}"
	install_data "${TEMPLATE_ROOT}/${ENGINE_DIRECTORY}" "${BUILTDIR}"

	for f in ${PACKAGING_COPY_ENGINE_FILES}; do
		mkdir -p "${BUILTDIR}/$(dirname "${f}")"
		cp -r "${TEMPLATE_ROOT}/${ENGINE_DIRECTORY}/${f}" "${BUILTDIR}/${f}"
	done

	echo "Building mod files (${PLATFORM})"
	install_mod_assemblies "${TEMPLATE_ROOT}" "${BUILTDIR}" "win-${PLATFORM}" "net6" "${TEMPLATE_ROOT}/${ENGINE_DIRECTORY}"

	cp -Lr "${TEMPLATE_ROOT}/mods/"* "${BUILTDIR}/mods"

	set_engine_version "${ENGINE_VERSION}" "${BUILTDIR}"
	if [ "${PACKAGING_OVERWRITE_MOD_VERSION}" == "True" ]; then
		set_mod_version "${TAG}" "${BUILTDIR}/mods/${MOD_ID}/mod.yaml"
	else
		MOD_VERSION=$(grep 'Version:' "mods/${MOD_ID}/mod.yaml" | awk '{print $2}')
		echo "Mod version ${MOD_VERSION} will remain unchanged.";
	fi

	TAG_TYPE="${TAG%%-*}"
	TAG_VERSION="${TAG#*-}"
	BACKWARDS_TAG="${TAG_VERSION}-${TAG_TYPE}"

	# Create multi-resolution icon
	${MAGICK} "${ARTWORK_DIR}/icon_16x16.png" "${ARTWORK_DIR}/icon_24x24.png" "${ARTWORK_DIR}/icon_32x32.png" "${ARTWORK_DIR}/icon_48x48.png" "${ARTWORK_DIR}/icon_256x256.png" "${BUILTDIR}/${MOD_ID}.ico"

	# Installer wizard artwork, rebuilt from the mod's key art on every package run.
	echo "Generating installer artwork (${PLATFORM})"
	"${PACKAGING_DIR}/generate-theme.sh" "${MAGICK}" \
		"$(topath "${TEMPLATE_ROOT}/${PACKAGING_WINDOWS_THEME_ART}")" \
		"${PACKAGING_WINDOWS_THEME_LOGO_CROP}" \
		"${PACKAGING_WINDOWS_THEME_BACKDROP_CROP}" \
		"$(topath "${TEMPLATE_ROOT}/${PACKAGING_WINDOWS_THEME_FONT}")" \
		"${PACKAGING_WINDOWS_THEME_BG}" \
		"${PACKAGING_WINDOWS_THEME_ACCENT}" \
		"${TAG}" \
		"$(topath "${THEME_DIR}")"

	echo "Compiling Windows launcher (${PLATFORM})"
	install_windows_launcher "${TEMPLATE_ROOT}/${ENGINE_DIRECTORY}" "${BUILTDIR}" "win-${PLATFORM}" "${MOD_ID}" "${PACKAGING_WINDOWS_LAUNCHER_NAME}" "${PACKAGING_DISPLAY_NAME}" "${PACKAGING_FAQ_URL}" "${TAG}"

	# Use rcedit to patch the generated EXE with missing assembly/PortableExecutable information because .NET 6 ignores that when building on Linux.
	# Using a backwards version tag because rcedit is unable to set versions starting with a letter.
	${RCEDIT} "${BUILTDIR}/${PACKAGING_WINDOWS_LAUNCHER_NAME}.exe" --set-product-version "${BACKWARDS_TAG}"
	${RCEDIT} "${BUILTDIR}/${PACKAGING_WINDOWS_LAUNCHER_NAME}.exe" --set-version-string "ProductName" "OpenRA"
	${RCEDIT} "${BUILTDIR}/${PACKAGING_WINDOWS_LAUNCHER_NAME}.exe" --set-version-string "CompanyName" "The OpenRA team"
	${RCEDIT} "${BUILTDIR}/${PACKAGING_WINDOWS_LAUNCHER_NAME}.exe" --set-version-string "FileDescription" "${PACKAGING_WINDOWS_LAUNCHER_NAME} mod for OpenRA"
	${RCEDIT} "${BUILTDIR}/${PACKAGING_WINDOWS_LAUNCHER_NAME}.exe" --set-version-string "LegalCopyright" "Copyright (c) The OpenRA Developers and Contributors"
	${RCEDIT} "${BUILTDIR}/${PACKAGING_WINDOWS_LAUNCHER_NAME}.exe" --set-icon "${BUILTDIR}/${MOD_ID}.ico"

	echo "Building Windows setup.exe (${PLATFORM})"
	pushd "${PACKAGING_DIR}" > /dev/null
	makensis -V2 \
		-DSRCDIR="$(topath "${BUILTDIR}")" \
		-DTHEME_DIR="$(topath "${THEME_DIR}")" \
		-DTAG="${TAG}" \
		-DMOD_ID="${MOD_ID}" \
		-DPACKAGING_WINDOWS_INSTALL_DIR_NAME="${PACKAGING_WINDOWS_INSTALL_DIR_NAME}" \
		-DPACKAGING_WINDOWS_LAUNCHER_NAME="${PACKAGING_WINDOWS_LAUNCHER_NAME}" \
		-DPACKAGING_DISPLAY_NAME="${PACKAGING_DISPLAY_NAME}" \
		-DPACKAGING_WEBSITE_URL="${PACKAGING_WEBSITE_URL}" \
		-DPACKAGING_AUTHORS="${PACKAGING_AUTHORS}" \
		-DPACKAGING_WINDOWS_REGISTRY_KEY="${PACKAGING_WINDOWS_REGISTRY_KEY}" \
		-DPACKAGING_WINDOWS_LICENSE_FILE="$(topath "${TEMPLATE_ROOT}/${PACKAGING_WINDOWS_LICENSE_FILE}")" \
		-DTHEME_BGCOLOR="${PACKAGING_WINDOWS_THEME_BG}" \
		-DTHEME_TEXTCOLOR="${PACKAGING_WINDOWS_THEME_TEXT}" \
		-DTHEME_ACCENTCOLOR="${PACKAGING_WINDOWS_THEME_ACCENT}" \
		-DTHEME_ACCENT_BGR="$(to_bgr "${PACKAGING_WINDOWS_THEME_ACCENT}")" \
		-DTHEME_BG_BGR="$(to_bgr "${PACKAGING_WINDOWS_THEME_BG}")" \
		-DOUTFILE="$(topath "${OUTPUTDIR}/${PACKAGING_INSTALLER_NAME}-${TAG}-${PLATFORM}.exe")" \
		${USE_PROGRAMFILES32} ${USE_DISCORDID} buildpackage.nsi
	popd > /dev/null

	echo "Packaging portable archive (${PLATFORM})"
	ARCHIVE="${OUTPUTDIR}/${PACKAGING_INSTALLER_NAME}-${TAG}-${PLATFORM}-winportable.zip"
	rm -f "${ARCHIVE}"
	pushd "${BUILTDIR}" > /dev/null
	if command -v zip >/dev/null 2>&1; then
		zip "${ARCHIVE}" -r -9 ./* --quiet
	elif command -v 7z >/dev/null 2>&1; then
		7z a -tzip -mx=9 "$(topath "${ARCHIVE}")" ./* > /dev/null
	elif [ "${HOST_WINDOWS}" = "True" ]; then
		# Neither archiver is present, but Windows always has this one.
		powershell -NoProfile -Command \
			"Compress-Archive -Path '*' -DestinationPath '$(topath "${ARCHIVE}")' -CompressionLevel Optimal -Force"
	else
		echo >&2 "No zip tool found -- skipping the portable archive."
	fi
	popd > /dev/null

	# Cleanup
	rm -rf "${BUILTDIR}"
}

for PLATFORM in ${PACKAGING_WINDOWS_PLATFORMS}; do
	build_platform "${PLATFORM}"
done
