#!/usr/bin/env bash
# MacTahoe KDE — step-wallpapers (online installer step)
set -uo pipefail

DEST="src/steps/wallpapers"
BASE="https://512pixels.net/downloads/macos-wallpapers-6k"
BASE_OLD="https://512pixels.net/downloads/macos-wallpapers"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; RESET='\033[0m'

ok()        { echo -e "  ${GREEN}✓${RESET}  $*"; }
reinstall() { echo -e "  ${YELLOW}↺${RESET}  $* (reinstalled)"; }
fail()      { echo -e "  ${RED}✗${RESET}  $*"; }

[[ -d "src" ]] || { echo -e "${RED}  Run from repo root.${RESET}" >&2; exit 1; }
mkdir -p "$DEST"

get() {
  local url="$1" dest="$2" name="$3"
  mkdir -p "$(dirname "$dest")"
  if [[ -f "$dest" ]]; then
    curl -fsSL --retry 3 \
      -H "Referer: https://512pixels.net/projects/default-mac-wallpapers-in-5k/" \
      -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" \
      -o "$dest" "$url" 2>/dev/null && reinstall "$name" || fail "$name"
  else
    curl -fsSL --retry 3 \
      -H "Referer: https://512pixels.net/projects/default-mac-wallpapers-in-5k/" \
      -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" \
      -o "$dest" "$url" 2>/dev/null && ok "$name (installed)" || { rm -f "$dest"; fail "$name"; }
  fi
}

meta() {
  local dir="$1" id="$2" name="$3" desc="$4" auto="${5:-false}"
  mkdir -p "$dir/contents/images"
  $auto && mkdir -p "$dir/contents/images_dark"
  cat > "$dir/metadata.json" << METAEOF
{
    "KPlugin": {
        "Id": "${id}",
        "Name": "${name}",
        "Description": "${desc}",
        "Authors": [{ "Name": "MacTahoe KDE", "Email": "" }],
        "Category": "MacTahoe KDE",
        "License": "Apple Inc. wallpapers extracted from macOS",
        "Website": "https://github.com/lester-sudo/macos-tahoe-liquid-kde",
        "Version": "1.0"
    }
}
METAEOF
}

# Tahoe Liquid Glass
dir="$DEST/MacTahoe"
meta "$dir" "MacTahoe" "macOS Tahoe" "Liquid Glass — auto light/dark" true
get "$BASE/26-Tahoe-Light-6K.png" "$dir/contents/images/3840x2160.png"      "MacTahoe — Light"
get "$BASE/26-Tahoe-Dark-6K.png"  "$dir/contents/images_dark/3840x2160.png" "MacTahoe — Dark"

# Beach series
declare -A BEACH=(
  ["MacTahoe-Beach-Dawn"]="26-Tahoe-Beach-Dawn.png|Tahoe Beach — Dawn"
  ["MacTahoe-Beach-Day"]="26-Tahoe-Beach-Day.png|Tahoe Beach — Day"
  ["MacTahoe-Beach-Dusk"]="26-Tahoe-Beach-Dusk.png|Tahoe Beach — Dusk"
  ["MacTahoe-Beach-Night"]="26-Tahoe-Beach-Night.png|Tahoe Beach — Night"
)
for id in "${!BEACH[@]}"; do
  IFS='|' read -r file name <<< "${BEACH[$id]}"
  dir="$DEST/$id"
  meta "$dir" "$id" "$name" "Lake Tahoe landscape"
  get "$BASE/$file" "$dir/contents/images/3840x2160.${file##*.}" "$id"
done

# Landscape series (zip)
ZIP_URL="https://lowendmac.com/wp-content/uploads/Lake-Tahoe-macOS-26-Beta-5-wallpapers.zip"
TMP="/tmp/tahoe-wp-$$"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP"
if curl -fsSL --retry 3 -o "$TMP/landscape.zip" "$ZIP_URL" 2>/dev/null; then
  unzip -q "$TMP/landscape.zip" -d "$TMP/out"
  i=1
  while IFS= read -r -d '' img; do
    raw=$(basename "${img%.*}")
    id="MacTahoe-Landscape-$(printf '%02d' $i)"
    dir="$DEST/$id"
    meta "$dir" "$id" "Tahoe Landscape — $raw" "Lake Tahoe landscape"
    dest="$dir/contents/images/3840x2160.${img##*.}"
    [[ -f "$dest" ]] && { cp "$img" "$dest"; reinstall "$id — $raw"; } \
                     || { cp "$img" "$dest"; ok "$id — $raw (installed)"; }
    ((i++))
  done < <(find "$TMP/out" -type f \( -iname "*.jpg" -o -iname "*.png" \) -print0 | sort -z)
else
  fail "landscape zip — $ZIP_URL"
fi

# Heritage pairs
declare -A PAIRS=(
  ["MacHeritage-Sequoia"]="$BASE/15-Sequoia-Light-6K.jpg|$BASE/15-Sequoia-Dark-6K.jpg|macOS Sequoia"
  ["MacHeritage-Sonoma"]="$BASE/14-Sonoma-Light.jpg|$BASE/14-Sonoma-Dark.jpg|macOS Sonoma"
  ["MacHeritage-Ventura"]="$BASE/13-Ventura-Light.jpg|$BASE/13-Ventura-Dark.jpg|macOS Ventura"
  ["MacHeritage-Monterey"]="$BASE/12-Light.jpg|$BASE/12-Dark.jpg|macOS Monterey"
  ["MacHeritage-BigSur"]="$BASE_OLD/11-0-Color-Day.jpg|$BASE_OLD/11-0-Big-Sur-Color-Night.jpg|macOS Big Sur"
)
for id in "${!PAIRS[@]}"; do
  IFS='|' read -r url_l url_d name <<< "${PAIRS[$id]}"
  dir="$DEST/$id"
  meta "$dir" "$id" "$name" "$name — auto light/dark" true
  get "$url_l" "$dir/contents/images/3840x2160.${url_l##*.}"      "$id — Light"
  get "$url_d" "$dir/contents/images_dark/3840x2160.${url_d##*.}" "$id — Dark"
done

declare -A SINGLES=(
  ["MacHeritage-Sequoia-Sunrise"]="$BASE/15-Sequoia-Sunrise.png|macOS Sequoia — Sunrise"
  ["MacHeritage-Sonoma-Horizon"]="$BASE/14-Sonoma-Horizon.png|macOS Sonoma — Horizon"
)
for id in "${!SINGLES[@]}"; do
  IFS='|' read -r url name <<< "${SINGLES[$id]}"
  dir="$DEST/$id"
  meta "$dir" "$id" "$name" "$name"
  get "$url" "$dir/contents/images/3840x2160.${url##*.}" "$id"
done

echo ""
total=$(find "$DEST" -name "metadata.json" 2>/dev/null | wc -l)
ok "$total wallpaper packages ready"