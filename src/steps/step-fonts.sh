#!/usr/bin/env bash
# MacTahoe KDE — step-fonts (online installer step)
set -uo pipefail

DEST="src/steps/fonts"
ZIP_URL="https://github.com/sahibjotsaggu/San-Francisco-Pro-Fonts/archive/refs/heads/master.zip"
TMP="/tmp/tahoe-fonts-$$"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; RESET='\033[0m'

ok()        { echo -e "  ${GREEN}✓${RESET}  $*"; }
reinstall() { echo -e "  ${YELLOW}↺${RESET}  $* (updated)"; }
fail()      { echo -e "  ${RED}✗${RESET}  $*"; }

[[ -d "src" ]] || { echo -e "${RED}  Run from repo root.${RESET}" >&2; exit 1; }

trap 'rm -rf "$TMP"' EXIT
mkdir -p "$DEST" "$TMP"

if ! curl -fsSL --retry 3 \
    -H "User-Agent: Mozilla/5.0" \
    -o "$TMP/fonts.zip" "$ZIP_URL" 2>/dev/null; then
  fail "download failed — check your connection"
  exit 1
fi

unzip -q "$TMP/fonts.zip" -d "$TMP/out"

while IFS= read -r -d '' f; do
  name=$(basename "$f")
  if [[ -f "$DEST/$name" ]]; then
    if err=$(cp "$f" "$DEST/$name" 2>&1); then
      reinstall "$name"
    else
      fail "$name (copy failed: ${err:-unknown error})"
    fi
  else
    if err=$(cp "$f" "$DEST/$name" 2>&1); then
      ok "$name (installed)"
    else
      fail "$name (copy failed: ${err:-unknown error})"
    fi
  fi
done < <(find "$TMP/out" -type f \( -iname "*.otf" -o -iname "*.ttf" \) -print0 | sort -z)