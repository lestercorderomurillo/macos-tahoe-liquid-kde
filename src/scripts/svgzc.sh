#!/usr/bin/env bash
# Decode SVGZ → SVG for editing, then recompile SVG → SVGZ when done.
# Decoded SVGs go into svg-edit/ at the repo root:
#
#   svg-edit/
#     Dark/widgets/button.svg
#     Dark/dialogs/background.svg
#     Light/widgets/button.svg
#     ...
#
# Usage:
#   src/scripts/svgzc.sh decode          Decode all .svgz → svg-edit/
#   src/scripts/svgzc.sh decode <file>   Decode one .svgz file
#   src/scripts/svgzc.sh encode          Recompile all edited .svg back to .svgz
#   src/scripts/svgzc.sh encode <file>   Recompile one .svg from svg-edit/
#   src/scripts/svgzc.sh clean           Remove the svg-edit/ directory

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLASMA_THEME="$REPO/src/offline/plasma-theme"
EDIT_DIR="$REPO/svg-edit"

# MacTahoeLiquidKde-Dark → Dark, MacTahoeLiquidKde-Light → Light
_short_variant() {
  local path="$1"
  if [[ "$path" == *"-Dark"* ]]; then echo "Dark"
  elif [[ "$path" == *"-Light"* ]]; then echo "Light"
  else echo "Other"
  fi
}

# relative path after the theme variant dir (e.g. widgets/button.svgz)
_inner_path() {
  local path="$1"
  echo "$path" | sed 's|.*/MacTahoeLiquidKde-[^/]*/||'
}

# svg-edit/Dark/widgets/button.svg → .../MacTahoeLiquidKde-Dark/widgets/button.svgz
_svg_to_svgz() {
  local svg="$1"
  local rel="${svg#"$EDIT_DIR/"}"
  local variant="${rel%%/*}"
  local inner="${rel#*/}"
  local full_variant
  case "$variant" in
    Dark)  full_variant="MacTahoeLiquidKde-Dark" ;;
    Light) full_variant="MacTahoeLiquidKde-Light" ;;
    *)     echo "  skip (unknown variant $variant): $svg"; return 1 ;;
  esac
  echo "$PLASMA_THEME/$full_variant/${inner%.svg}.svgz"
}

decode_one() {
  local svgz="$1"
  local variant inner svg
  variant=$(_short_variant "$svgz")
  inner=$(_inner_path "$svgz")
  svg="$EDIT_DIR/$variant/${inner%.svgz}.svg"
  mkdir -p "$(dirname "$svg")"
  gunzip -c "$svgz" > "$svg"
  echo "  decoded: $svg"
}

encode_one() {
  local svg="$1"
  local svgz
  svgz=$(_svg_to_svgz "$svg") || return
  [[ -f "$svgz" ]] || { echo "  skip (no matching .svgz): $svgz"; return; }
  gzip -9cn "$svg" > "$svgz"
  echo "  encoded: $svgz"
}

decode_all() {
  local count=0
  while IFS= read -r -d '' f; do
    decode_one "$f"
    count=$((count + 1))
  done < <(find "$PLASMA_THEME" -name '*.svgz' -print0)
  echo "Decoded $count files into $EDIT_DIR/"
  echo "Edit the .svg files, then run: $0 encode"
}

encode_all() {
  local count=0
  while IFS= read -r -d '' f; do
    encode_one "$f"
    count=$((count + 1))
  done < <(find "$EDIT_DIR" -name '*.svg' -print0)
  echo "Encoded $count files. Run: $0 clean"
}

clean() {
  rm -rf "$EDIT_DIR"
  echo "Removed $EDIT_DIR/"
}

case "${1:-}" in
  decode)
    if [[ -n "${2:-}" ]]; then
      decode_one "$2"
    else
      decode_all
    fi
    ;;
  encode)
    if [[ -n "${2:-}" ]]; then
      encode_one "$2"
    else
      encode_all
    fi
    ;;
  clean)
    clean
    ;;
  *)
    echo "Usage: $0 {decode|encode|clean} [file]"
    exit 1
    ;;
esac
