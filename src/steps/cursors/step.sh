#!/usr/bin/env bash
# MacTahoe Liquid KDE — cursors step

DEST="$STEPS/cursors"
DEST_DIR="$HOME/.local/share/icons"
MIRROR_FILE="$SRC/mirrors/cursors.json"

deps() {
  echo "curl"
  echo "unzip"
}

download() {
  TMP="/tmp/tahoe-cursors-$$"
  trap 'rm -rf "$TMP"' RETURN
  mkdir -p "$TMP"

  rm -rf "$DEST"/MacTahoeLiquidKde*
  mkdir -p "$DEST"

  handle_mirror() {
    local xdir="$1" prefix="$2" installed=false
    while IFS= read -r -d '' dir; do
      [[ -d "$dir/cursors" && -f "$dir/index.theme" ]] || continue
      [[ $(find "$dir/cursors" -maxdepth 1 -type f 2>/dev/null | wc -l) -gt 0 ]] || continue
      local raw name
      raw=$(basename "$dir")
      case "$raw" in
        *[Ww]hite*)              name="${prefix}-White" ;;
        *[Dd]ark*|*-dark)        name="${prefix}-Dark" ;;
        dist|macOS|macos|MacOS)  name="$prefix" ;;
        *)
          [[ "$raw" == *-main || "$raw" == *-master ]] && continue
          name="${prefix}-${raw}"
          ;;
      esac
      rm -rf "$DEST/$name"
      cp -r "$dir" "$DEST/$name" 2>/dev/null && installed=true || fail "$name (copy failed)"
    done < <(find "$xdir" -mindepth 1 -maxdepth 5 -type d -print0 2>/dev/null)
    $installed
  }

  local any_ok=false
  local count
  count=$(json_source_count "$MIRROR_FILE")
  for ((s=0; s<count; s++)); do
    run_mirrors "$MIRROR_FILE" "$s" && any_ok=true
  done

  $any_ok || { fail "no cursor themes installed — all mirrors failed"; return 1; }
}

install() {
  # snapshot before
  declare -A pre=()
  for d in "$DEST_DIR"/*/; do [[ -d "$d" ]] && pre["$(basename "$d")"]=1; done

  mkdir -p "$DEST_DIR"
  local n_inst=0 n_re=0
  for theme in "$DEST"/Mac*/; do
    [[ -d "$theme" ]] || continue
    local name
    name=$(basename "$theme")
    [[ -d "$theme/cursors" ]] || { fail "$name (no cursors/ dir — skipping)"; continue; }

    if safe_copy "$theme" "$DEST_DIR/$name"; then
      if [[ -n "${pre[$name]+_}" ]]; then
        reinstall "$name"; n_re=$((n_re+1))
      else
        ok "$name (installed)"; n_inst=$((n_inst+1))
      fi
    else
      fail "$name (copy failed)"
    fi
  done
  info "$((n_inst+n_re)) cursor themes — $n_inst installed, $n_re reinstalled"
}

uninstall() {
  local n=0
  for theme in "$DEST_DIR"/MacTahoeLiquidKde*; do
    [[ -d "$theme" ]] || continue
    local name
    name=$(basename "$theme")
    [[ "$name" == *Icons* ]] && continue
    rm -rf "$theme" 2>/dev/null && ok "$name" && n=$((n+1)) || fail "$name"
  done
  info "$n cursor themes removed"
}
