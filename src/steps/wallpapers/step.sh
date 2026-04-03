#!/usr/bin/env bash
# MacTahoe Liquid KDE — wallpapers step

DEST="$STEPS/wallpapers"
DEST_DIR="$HOME/.local/share/wallpapers"
MIRROR_FILE="$SRC/mirrors/wallpapers.json"

deps() {
  echo "curl"
  echo "unzip"
}

# ── helpers ──────────────────────────────────────────────────────
wp_meta() {
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

wp_get() {
  local url="$1" dest="$2" name="$3" referer="$4"
  mkdir -p "$(dirname "$dest")"
  fetch "$url" "$dest" "$referer" || { rm -f "$dest"; fail "$name (download failed)"; }
}

download() {
  TMP="/tmp/tahoe-wp-$$"
  trap 'rm -rf "$TMP"' RETURN
  mkdir -p "$DEST" "$TMP"

  # read base URLs from source 0 mirrors
  local base base_old referer
  base=$(json_mirrors "$MIRROR_FILE" 0 | head -1 | cut -f1)
  base_old=$(json_mirrors "$MIRROR_FILE" 0 | tail -1 | cut -f1)
  referer=$(json_mirrors "$MIRROR_FILE" 0 | head -1 | cut -f4)

  # ── Tahoe ──────────────────────────────────────────────────
  local dir="$DEST/MacTahoe"
  wp_meta "$dir" "MacTahoe" "macOS Tahoe" "Auto light/dark wallpaper" true
  wp_get "$base/26-Tahoe-Light-6K.png" "$dir/contents/images/3840x2160.png"      "MacTahoe — Light" "$referer"
  wp_get "$base/26-Tahoe-Dark-6K.png"  "$dir/contents/images_dark/3840x2160.png" "MacTahoe — Dark"  "$referer"

  # ── Beach series ───────────────────────────────────────────
  local -a BEACH=(
    "MacTahoe-Beach-Dawn|26-Tahoe-Beach-Dawn.png|Tahoe Beach — Dawn"
    "MacTahoe-Beach-Day|26-Tahoe-Beach-Day.png|Tahoe Beach — Day"
    "MacTahoe-Beach-Dusk|26-Tahoe-Beach-Dusk.png|Tahoe Beach — Dusk"
    "MacTahoe-Beach-Night|26-Tahoe-Beach-Night.png|Tahoe Beach — Night"
  )
  for entry in "${BEACH[@]}"; do
    IFS='|' read -r id file name <<< "$entry"
    dir="$DEST/$id"
    wp_meta "$dir" "$id" "$name" "Lake Tahoe landscape"
    wp_get "$base/$file" "$dir/contents/images/3840x2160.${file##*.}" "$id" "$referer"
  done

  # ── Landscape series (zip from source 1) ───────────────────
  handle_mirror() {
    local xdir="$1" i=1
    while IFS= read -r -d '' img; do
      [[ "$(basename "$img")" == ._* ]] && continue
      local raw id dir dest
      raw=$(basename "${img%.*}")
      id="MacTahoe-Landscape-$(printf '%02d' $i)"
      dir="$DEST/$id"
      wp_meta "$dir" "$id" "Tahoe Landscape — $raw" "Lake Tahoe landscape"
      dest="$dir/contents/images/3840x2160.${img##*.}"
      cp "$img" "$dest" 2>/dev/null || fail "$id (copy failed)"
      ((i++))
    done < <(find "$xdir" -type f \( -iname "*.jpg" -o -iname "*.png" \) -print0 | sort -z)
    [[ $i -gt 1 ]]
  }
  run_mirrors "$MIRROR_FILE" 1 || fail "landscape zip — all mirrors failed"

  # ── Heritage pairs ─────────────────────────────────────────
  local -a PAIRS=(
    "MacHeritage-Sequoia|$base/15-Sequoia-Light-6K.jpg|$base/15-Sequoia-Dark-6K.jpg|macOS Sequoia"
    "MacHeritage-Sonoma|$base/14-Sonoma-Light.jpg|$base/14-Sonoma-Dark.jpg|macOS Sonoma"
    "MacHeritage-Ventura|$base/13-Ventura-Light.jpg|$base/13-Ventura-Dark.jpg|macOS Ventura"
    "MacHeritage-Monterey|$base/12-Light.jpg|$base/12-Dark.jpg|macOS Monterey"
    "MacHeritage-BigSur|$base_old/11-0-Color-Day.jpg|$base_old/11-0-Big-Sur-Color-Night.jpg|macOS Big Sur"
  )
  for entry in "${PAIRS[@]}"; do
    IFS='|' read -r id url_l url_d name <<< "$entry"
    dir="$DEST/$id"
    wp_meta "$dir" "$id" "$name" "$name — auto light/dark" true
    wp_get "$url_l" "$dir/contents/images/3840x2160.${url_l##*.}"      "$id — Light" "$referer"
    wp_get "$url_d" "$dir/contents/images_dark/3840x2160.${url_d##*.}" "$id — Dark"  "$referer"
  done

  # ── Heritage singles ───────────────────────────────────────
  local -a SINGLES=(
    "MacHeritage-Sequoia-Sunrise|$base/15-Sequoia-Sunrise.png|macOS Sequoia — Sunrise"
    "MacHeritage-Sonoma-Horizon|$base/14-Sonoma-Horizon.png|macOS Sonoma — Horizon"
  )
  for entry in "${SINGLES[@]}"; do
    IFS='|' read -r id url name <<< "$entry"
    dir="$DEST/$id"
    wp_meta "$dir" "$id" "$name" "$name"
    wp_get "$url" "$dir/contents/images/3840x2160.${url##*.}" "$id" "$referer"
  done
}

install() {
  # snapshot before so installed/reinstalled reflects pre-run state
  declare -A pre=()
  for d in "$DEST_DIR"/*/; do [[ -d "$d" ]] && pre["$(basename "$d")"]=1; done

  mkdir -p "$DEST_DIR"
  local n_inst=0 n_re=0
  for wp in "$DEST"/Mac*/; do
    [[ -d "$wp" ]] || continue
    local name img_count
    name=$(basename "$wp")

    img_count=$(find "$wp/contents" -type f 2>/dev/null | wc -l)
    if [[ $img_count -eq 0 ]]; then
      fail "$name (download incomplete — re-run to retry)"
      continue
    fi

    if safe_copy "$wp" "$DEST_DIR/$name"; then
      if [[ -n "${pre[$name]+_}" ]]; then
        reinstall "$name"; n_re=$((n_re+1))
      else
        ok "$name (installed)"; n_inst=$((n_inst+1))
      fi
    else
      fail "$name (copy failed)"
    fi
  done
  info "$((n_inst+n_re)) wallpapers — $n_inst installed, $n_re reinstalled"
}

uninstall() {
  local n=0
  for name in MacTahoe MacTahoe-Beach-Dawn MacTahoe-Beach-Day MacTahoe-Beach-Dusk MacTahoe-Beach-Night \
    MacHeritage-Sequoia MacHeritage-Sequoia-Sunrise MacHeritage-Sonoma MacHeritage-Sonoma-Horizon \
    MacHeritage-Ventura MacHeritage-Monterey MacHeritage-BigSur; do
    [[ -d "$DEST_DIR/$name" ]] || continue
    rm -rf "$DEST_DIR/$name" 2>/dev/null && ok "$name" && n=$((n+1)) || fail "$name"
  done
  for d in "$DEST_DIR"/MacTahoe-Landscape-*/; do
    [[ -d "$d" ]] || continue
    local name
    name=$(basename "$d")
    rm -rf "$d" 2>/dev/null && ok "$name" && n=$((n+1)) || fail "$name"
  done
  info "$n wallpapers removed"
}
