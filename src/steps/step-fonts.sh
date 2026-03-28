#!/usr/bin/env bash
# MacTahoe Liquid KDE — step-fonts (online installer step)
set -uo pipefail

DEST="src/steps/fonts"
TMP="/tmp/tahoe-fonts-$$"

source "$(dirname "$0")/utils.sh"

[[ -d "src" ]] || { echo -e "\033[0;31m  run from repo root.\033[0m" >&2; exit 1; }
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$DEST" "$TMP"

# ── mirrors ───────────────────────────────────────────────────
mapfile -t MIRRORS < <(grep '^mirror:' "src/mirrors/fonts.txt" | sed 's/^mirror: *//')

handle_mirror() {
  local xdir="$1" installed=false
  while IFS= read -r -d '' f; do
    local name
    name=$(basename "$f")
    cp "$f" "$DEST/$name" 2>/dev/null && installed=true || fail "$name (copy failed)"
  done < <(find "$xdir" -type f \( -iname "*.otf" -o -iname "*.ttf" \) -print0 | sort -z)
  $installed
}

run_mirrors || { fail "no fonts installed — all mirrors failed"; exit 1; }