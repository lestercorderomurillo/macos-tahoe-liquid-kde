#!/usr/bin/env bash
# MacTahoe Liquid KDE — fonts step

DEST="$STEPS/fonts"
DEST_DIR="$HOME/.local/share/fonts"
MIRROR_FILE="$SRC/mirrors/fonts.json"

deps() {
  echo "curl"
  echo "unzip"
  echo "fc-cache:fontconfig"
}

download() {
  TMP="/tmp/tahoe-fonts-$$"
  trap 'rm -rf "$TMP"' RETURN
  mkdir -p "$DEST" "$TMP"

  rm -f "$DEST"/*.otf "$DEST"/*.ttf

  handle_mirror() {
    local xdir="$1" installed=false
    while IFS= read -r -d '' f; do
      local name
      name=$(basename "$f")
      cp "$f" "$DEST/$name" 2>/dev/null && installed=true || fail "$name (copy failed)"
    done < <(find "$xdir" -type f \( -iname "*.otf" -o -iname "*.ttf" \) -print0 | sort -z)
    $installed
  }

  run_mirrors "$MIRROR_FILE" 0 || { fail "no fonts installed — all mirrors failed"; return 1; }
}

install() {
  mkdir -p "$DEST_DIR"
  declare -A g_inst=() g_re=()
  for f in "$DEST/"*.otf "$DEST/"*.ttf; do
    [[ -f "$f" ]] || continue
    local name grp
    name=$(basename "$f")
    if   [[ "$name" == SF-Mono* ]] || [[ "$name" == SFMono* ]]; then grp="SF Mono"
    elif [[ "$name" == SF-Pro*  ]] || [[ "$name" == SFPro*  ]]; then grp="SF Pro"
    else grp="Other"; fi

    if [[ -f "$DEST_DIR/$name" ]]; then
      if cp "$f" "$DEST_DIR/" 2>/dev/null; then
        reinstall "$name"; g_re[$grp]=$(( ${g_re[$grp]:-0} + 1 ))
      else
        fail "$name (copy failed)"
      fi
    else
      if cp "$f" "$DEST_DIR/" 2>/dev/null; then
        ok "$name (installed)"; g_inst[$grp]=$(( ${g_inst[$grp]:-0} + 1 ))
      else
        fail "$name (copy failed)"
      fi
    fi
  done

  for grp in "SF Pro" "SF Mono" "Other"; do
    local i=${g_inst[$grp]:-0} r=${g_re[$grp]:-0}
    [[ $((i+r)) -eq 0 ]] && continue
    info "$grp — $i installed, $r reinstalled"
  done
  fc-cache -f "$DEST_DIR" 2>/dev/null || true
}

uninstall() {
  local n=0
  for pattern in "SF-Pro*" "SF-Mono*" "SFPro*" "SFMono*"; do
    for f in "$DEST_DIR/"$pattern; do
      [[ -f "$f" ]] || continue
      rm -f "$f" 2>/dev/null && n=$((n+1))
    done
  done
  [[ $n -gt 0 ]] && fc-cache -f "$DEST_DIR" 2>/dev/null || true
  info "$n font files removed"
}
