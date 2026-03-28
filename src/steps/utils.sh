#!/usr/bin/env bash
# MacTahoe Liquid KDE — step utilities
# usage: source "$(dirname "$0")/utils.sh"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; RESET='\033[0m'

ok()        { echo -e "  ${GREEN}✓${RESET}  $*"; }
reinstall() { echo -e "  ${YELLOW}↺${RESET}  $* (reinstalled)"; }
warn()      { echo -e "  ${YELLOW}⚠${RESET}  $*"; }
fail()      { echo -e "  ${RED}✗${RESET}  $*"; }

# fetch url dest
fetch() {
  curl -fsSL --retry 3 --retry-delay 1 \
    -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" \
    -o "$2" "$1" 2>/dev/null
}

# extract file dest  (detects zip / tar.gz / tar.xz / tar.*)
extract() {
  local file="$1" dest="$2"
  mkdir -p "$dest"
  case "$file" in
    *.zip)            unzip -q "$file" -d "$dest" 2>/dev/null ;;
    *.tar.gz|*.tgz)  tar -xzf "$file" -C "$dest" 2>/dev/null ;;
    *.tar.xz)        tar -xJf "$file" -C "$dest" 2>/dev/null ;;
    *.tar.*)         tar -xf  "$file" -C "$dest" 2>/dev/null ;;
    *) return 1 ;;
  esac
}

# run_mirrors — loops MIRRORS array, calls handle_mirror() per entry, stops at first success
# MIRRORS format: "url|ext|prefix"   ext = zip | tar.gz | tar.xz | tar.*
# caller must define: handle_mirror(extract_dir, prefix) → returns 0 on success
# caller must set:    TMP (temp dir)
run_mirrors() {
  local i=0
  for entry in "${MIRRORS[@]}"; do
    IFS='|' read -r url ext prefix <<< "$entry"
    ((i++))
    local out="$TMP/mirror${i}.${ext}" xdir="$TMP/extract${i}"

    fetch "$url" "$out"    || continue
    extract "$out" "$xdir" || continue

    handle_mirror "$xdir" "$prefix" && { ok "mirror $i"; return 0; }
  done
  return 1
}