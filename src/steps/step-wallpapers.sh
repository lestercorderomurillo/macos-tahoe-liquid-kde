#!/usr/bin/env bash
# MacTahoe Liquid KDE — step-wallpapers (online installer step)
set -uo pipefail

DEST="src/steps/wallpapers"
TMP="/tmp/tahoe-wp-$$"
BASE=$(grep '^base:' "src/mirrors/wallpapers.txt" | head -1 | sed 's/^base: *//')
BASE_OLD=$(grep '^base_old:' "src/mirrors/wallpapers.txt" | head -1 | sed 's/^base_old: *//')
REFERER=$(grep '^referer:' "src/mirrors/wallpapers.txt" | head -1 | sed 's/^referer: *//')

source "$(dirname "$0")/utils.sh"

[[ -d "src" ]] || { echo -e "\033[0;31m  run from repo root.\033[0m" >&2; exit 1; }
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$DEST" "$TMP"

# get url dest name — silent on success, fail() on error
get() {
  local url="$1" dest="$2" name="$3"
  mkdir -p "$(dirname "$dest")"
  curl -fsSL --retry 3 --retry-delay 1 \
    -H "Referer: $REFERER" \
    -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" \
    -o "$dest" "$url" 2>/dev/null \
    || { rm -f "$dest"; fail "$name (download failed)"; }
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
        "Authors": [{ "Name": "MacTahoe Liquid KDE", "Email": "" }],
        "Category": "MacTahoe Liquid KDE",
        "License": "Apple Inc. wallpapers extracted from macOS",
        "Website": "https://github.com/lester-sudo/macos-tahoe-liquid-kde",
        "Version": "1.0"
    }
}
METAEOF
}

# ── Tahoe Liquid Glass ────────────────────────────────────────
dir="$DEST/MacTahoe"
meta "$dir" "MacTahoe" "macOS Tahoe" "Liquid Glass — auto light/dark" true
get "$BASE/26-Tahoe-Light-6K.png" "$dir/contents/images/3840x2160.png"      "MacTahoe — Light"
get "$BASE/26-Tahoe-Dark-6K.png"  "$dir/contents/images_dark/3840x2160.png" "MacTahoe — Dark"

# ── Beach series ──────────────────────────────────────────────
BEACH=(
  "MacTahoe-Beach-Dawn|26-Tahoe-Beach-Dawn.png|Tahoe Beach — Dawn"
  "MacTahoe-Beach-Day|26-Tahoe-Beach-Day.png|Tahoe Beach — Day"
  "MacTahoe-Beach-Dusk|26-Tahoe-Beach-Dusk.png|Tahoe Beach — Dusk"
  "MacTahoe-Beach-Night|26-Tahoe-Beach-Night.png|Tahoe Beach — Night"
)
for entry in "${BEACH[@]}"; do
  IFS='|' read -r id file name <<< "$entry"
  dir="$DEST/$id"
  meta "$dir" "$id" "$name" "Lake Tahoe landscape"
  get "$BASE/$file" "$dir/contents/images/3840x2160.${file##*.}" "$id"
done

# ── Landscape series (zip with mirrors) ───────────────────────
mapfile -t MIRRORS < <(grep '^mirror:' "src/mirrors/wallpapers.txt" | sed 's/^mirror: *//')

handle_mirror() {
  local xdir="$1" i=1
  while IFS= read -r -d '' img; do
    [[ "$(basename "$img")" == ._* ]] && continue
    local raw id dir dest
    raw=$(basename "${img%.*}")
    id="MacTahoe-Landscape-$(printf '%02d' $i)"
    dir="$DEST/$id"
    meta "$dir" "$id" "Tahoe Landscape — $raw" "Lake Tahoe landscape"
    dest="$dir/contents/images/3840x2160.${img##*.}"
    cp "$img" "$dest" 2>/dev/null || fail "$id (copy failed)"
    ((i++))
  done < <(find "$xdir" -type f \( -iname "*.jpg" -o -iname "*.png" \) -print0 | sort -z)
  [[ $i -gt 1 ]]
}

run_mirrors || fail "landscape zip — all mirrors failed"

# ── Heritage pairs ────────────────────────────────────────────
PAIRS=(
  "MacHeritage-Sequoia|$BASE/15-Sequoia-Light-6K.jpg|$BASE/15-Sequoia-Dark-6K.jpg|macOS Sequoia"
  "MacHeritage-Sonoma|$BASE/14-Sonoma-Light.jpg|$BASE/14-Sonoma-Dark.jpg|macOS Sonoma"
  "MacHeritage-Ventura|$BASE/13-Ventura-Light.jpg|$BASE/13-Ventura-Dark.jpg|macOS Ventura"
  "MacHeritage-Monterey|$BASE/12-Light.jpg|$BASE/12-Dark.jpg|macOS Monterey"
  "MacHeritage-BigSur|$BASE_OLD/11-0-Color-Day.jpg|$BASE_OLD/11-0-Big-Sur-Color-Night.jpg|macOS Big Sur"
)
for entry in "${PAIRS[@]}"; do
  IFS='|' read -r id url_l url_d name <<< "$entry"
  dir="$DEST/$id"
  meta "$dir" "$id" "$name" "$name — auto light/dark" true
  get "$url_l" "$dir/contents/images/3840x2160.${url_l##*.}"      "$id — Light"
  get "$url_d" "$dir/contents/images_dark/3840x2160.${url_d##*.}" "$id — Dark"
done

# ── Heritage singles ──────────────────────────────────────────
SINGLES=(
  "MacHeritage-Sequoia-Sunrise|$BASE/15-Sequoia-Sunrise.png|macOS Sequoia — Sunrise"
  "MacHeritage-Sonoma-Horizon|$BASE/14-Sonoma-Horizon.png|macOS Sonoma — Horizon"
)
for entry in "${SINGLES[@]}"; do
  IFS='|' read -r id url name <<< "$entry"
  dir="$DEST/$id"
  meta "$dir" "$id" "$name" "$name"
  get "$url" "$dir/contents/images/3840x2160.${url##*.}" "$id"
done