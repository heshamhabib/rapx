#!/bin/sh
# Generate the Windows installer artwork from the mod's own menu key art, so that
# setup looks like the game instead of the stock grey NSIS wizard.
#
# Everything here is derived at build time from files already in the repository --
# no pre-rendered bitmaps are committed.
#
# Usage: generate-theme.sh MAGICK ART LOGO_CROP BACKDROP_CROP FONT BG ACCENT TAG OUT_DIR

set -e

MAGICK="${1}"
ART="${2}"
LOGO_CROP="${3}"
BACKDROP_CROP="${4}"
FONT="${5}"
BG="#${6}"
ACCENT="#${7}"
TAG="${8}"
OUT_DIR="${9}"

[ -f "${ART}" ] || { echo >&2 "Installer theme art not found: ${ART}"; exit 1; }
[ -f "${FONT}" ] || { echo >&2 "Installer theme font not found: ${FONT}"; exit 1; }

mkdir -p "${OUT_DIR}"
WORK="${OUT_DIR}/.work"
rm -rf "${WORK}"
mkdir -p "${WORK}"

# MUI sizes its bitmaps in dialog units: 164x314 for the welcome/finish sidebar and
# 150x57 for the page header. Rendering at 3x keeps them sharp on HiDPI displays,
# where NSIS scales the control up (the installer is manifested DPI aware).
SIDEBAR_W=492
SIDEBAR_H=942
HEADER_W=450
HEADER_H=171

##############################################################################
# Welcome / finish sidebar
##############################################################################

# Backdrop: a tall, deliberately logo-free slice of the key art (the burning skyline),
# darkened and softened so it reads as atmosphere behind the UI rather than competing
# with the wizard text beside it. A centred slice would instead pull in a second,
# clipped copy of the logo and ghost it behind the crisp one composited below.
${MAGICK} "${ART}" \
	-crop "${BACKDROP_CROP}" +repage \
	-resize "${SIDEBAR_W}x${SIDEBAR_H}!" \
	-brightness-contrast -12x6 \
	-blur 0x1.5 \
	"${WORK}/backdrop.png"

# Logo lockup, full panel width, flush to the top edge.
${MAGICK} "${ART}" -crop "${LOGO_CROP}" +repage -resize "${SIDEBAR_W}x" "${WORK}/lockup.png"
LOCKUP_H=$(${MAGICK} identify -format "%h" "${WORK}/lockup.png")
FADE_H=$(awk "BEGIN { printf \"%d\", ${LOCKUP_H} * 0.3 }")
SOLID_H=$((LOCKUP_H - FADE_H))

# Fade only the bottom edge: the other three sides sit flush against the panel, so
# there is no seam to hide there.
${MAGICK} -size "${SIDEBAR_W}x${SOLID_H}" xc:white \
	\( -size "${SIDEBAR_W}x${FADE_H}" gradient:white-black \) -append \
	"${WORK}/lockup-mask.png"

${MAGICK} "${WORK}/lockup.png" "${WORK}/lockup-mask.png" \
	-alpha off -compose CopyOpacity -composite \
	"${WORK}/lockup-faded.png"

# Vignette that sinks the lower part of the panel towards the background colour, giving
# the version stamp a clean place to sit. Held short of fully opaque so the embers stay
# faintly visible behind the text instead of the panel going flat black.
VIGNETTE_H=$((SIDEBAR_H * 2 / 5))
${MAGICK} -size "${SIDEBAR_W}x${VIGNETTE_H}" gradient:none-"${BG}" \
	-alpha set -channel A -evaluate multiply 0.88 +channel \
	"${WORK}/vignette.png"

${MAGICK} "${WORK}/backdrop.png" \
	"${WORK}/lockup-faded.png" -gravity north -compose over -composite \
	"${WORK}/vignette.png" -gravity south -compose over -composite \
	-font "${FONT}" \
	-gravity southwest -fill "${ACCENT}" -pointsize 34 -annotate +34+92 "${TAG}" \
	-gravity southwest -fill "#8A9196" -pointsize 24 -annotate +34+52 "Powered by OpenRA" \
	-gravity east -fill "${ACCENT}" \
	-draw "rectangle ${SIDEBAR_W},0 $((SIDEBAR_W - 4)),${SIDEBAR_H}" \
	-background "${BG}" -alpha remove -alpha off -type TrueColor \
	-define bmp:format=bmp3 \
	"BMP3:${OUT_DIR}/welcome.bmp"

##############################################################################
# Page header strip
##############################################################################

# Flat background matching MUI_BGCOLOR exactly, so the bitmap blends into the header
# strip with no visible seam next to the page title text.
LOGO_H=$((HEADER_H - 30))
${MAGICK} "${ART}" -crop "${LOGO_CROP}" +repage -resize "x${LOGO_H}" "${WORK}/header-logo.png"
LOGO_W=$(${MAGICK} identify -format "%w" "${WORK}/header-logo.png")

# The lockup carries its own slice of key art, which would otherwise land on the flat
# strip as a hard-edged rectangle. Feather all four edges so it reads as a backlit logo
# glowing out of the background instead of a pasted-in crop.
FEATHER=26
${MAGICK} -size "${LOGO_W}x${LOGO_H}" xc:black -fill white \
	-draw "rectangle ${FEATHER},${FEATHER} $((LOGO_W - FEATHER)),$((LOGO_H - FEATHER))" \
	-blur 0x14 \
	"${WORK}/header-mask.png"

${MAGICK} "${WORK}/header-logo.png" "${WORK}/header-mask.png" \
	-alpha off -compose CopyOpacity -composite \
	"${WORK}/header-logo-faded.png"

${MAGICK} -size "${HEADER_W}x${HEADER_H}" xc:"${BG}" \
	"${WORK}/header-logo-faded.png" -gravity center -geometry +0-6 -compose over -composite \
	-gravity south -fill "${ACCENT}" \
	-draw "rectangle 0,$((HEADER_H - 3)) ${HEADER_W},${HEADER_H}" \
	-background "${BG}" -alpha remove -alpha off -type TrueColor \
	-define bmp:format=bmp3 \
	"BMP3:${OUT_DIR}/header.bmp"

rm -rf "${WORK}"
