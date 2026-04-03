#!/usr/bin/env bash
# MacTahoe Liquid KDE — shared step utilities
# usage: source "$STEPS/lib.sh"

# ── logging ──────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; RESET='\033[0m'; BOLD='\033[1m'

ok()        { echo -e "  ${GREEN}✓${RESET}  $*"; }
reinstall() { echo -e "  ${YELLOW}↺${RESET}  $* (reinstalled)"; }
info()      { echo ""; echo -e "  ${BOLD}$*${RESET}"; }
note()      { echo -e "  $*"; echo ""; }
warn()      { echo -e "  ${YELLOW}⚠${RESET}  $*"; }
fail()      { echo -e "  ${RED}✗${RESET}  $*"; ERRORS+=("$*"); }

# ── json ─────────────────────────────────────────────────────────
# json_get file query
#   query is a python expression applied to the parsed object 'd'
#   examples: json_get file.json "d['name']"
#             json_get file.json "[m['url'] for s in d['sources'] for m in s['mirrors']]"
json_get() {
  python3 -c "
import json, sys
with open(sys.argv[1]) as f: d = json.load(f)
result = eval(sys.argv[2])
if isinstance(result, list):
    for item in result: print(item)
elif isinstance(result, bool):
    print('true' if result else 'false')
else:
    print(result)
" "$1" "$2"
}

# json_mirrors file source_index
#   prints mirror entries as tab-separated: url\tformat\tprefix\treferer
json_mirrors() {
  python3 -c "
import json, sys
with open(sys.argv[1]) as f: d = json.load(f)
src = d['sources'][int(sys.argv[2])]
for m in src.get('mirrors', []):
    parts = [m['url'], m.get('format','zip'), m.get('prefix',''), m.get('referer','')]
    print('\t'.join(parts))
" "$1" "$2"
}

# json_source_count file — prints number of sources
json_source_count() {
  python3 -c "
import json, sys
with open(sys.argv[1]) as f: d = json.load(f)
print(len(d['sources']))
" "$1"
}

# ── network ──────────────────────────────────────────────────────
# fetch url dest [referer]
fetch() {
  local url="$1" dest="$2" referer="${3:-}"
  local -a args=(curl -fsSL --retry 3 --retry-delay 1
    -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    -o "$dest")
  [[ -n "$referer" ]] && args+=(-H "Referer: $referer")
  "${args[@]}" "$url" 2>/dev/null
}

# ── archive ──────────────────────────────────────────────────────
# extract file dest — auto-detect zip/tar.gz/tar.xz
extract() {
  local file="$1" dest="$2"
  mkdir -p "$dest"
  case "$file" in
    *.zip)           unzip -q "$file" -d "$dest" 2>/dev/null ;;
    *.tar.gz|*.tgz)  tar -xzf "$file" -C "$dest" 2>/dev/null ;;
    *.tar.xz)        tar -xJf "$file" -C "$dest" 2>/dev/null ;;
    *.tar.*)         tar -xf  "$file" -C "$dest" 2>/dev/null ;;
    *) return 1 ;;
  esac
}

# ── mirror runner ────────────────────────────────────────────────
# run_mirrors json_file source_index
#   caller must define: handle_mirror(extract_dir, prefix) → returns 0 on success
#   caller must set: TMP (temp dir)
run_mirrors() {
  local json_file="$1" source_idx="${2:-0}" i=0
  while IFS=$'\t' read -r url format prefix referer; do
    ((i++))
    local out="$TMP/mirror${i}.${format}" xdir="$TMP/extract${i}"

    if [[ "$format" == "base" ]]; then
      # base URL — pass directly to handler, no download/extract
      handle_mirror "$url" "$prefix" "$referer" && { ok "mirror $i"; return 0; }
      continue
    fi

    fetch "$url" "$out" "$referer" || continue
    extract "$out" "$xdir"         || continue

    handle_mirror "$xdir" "$prefix" && { ok "mirror $i"; return 0; }
  done < <(json_mirrors "$json_file" "$source_idx")
  return 1
}

# ── install helpers ──────────────────────────────────────────────
# safe_copy src dest — atomic copy via tmp + mv
safe_copy() {
  local src="$1" dest="$2"
  local name tmp bak
  name=$(basename "$dest")
  tmp="${dest%/*}/.tmp_${name}_$$"
  bak="${dest%/*}/.bak_${name}_$$"

  rm -rf "$tmp" 2>/dev/null || true
  if cp -r "$src/." "$tmp/" 2>/dev/null || { mkdir -p "$tmp" && cp -r "$src/." "$tmp/"; }; then
    rm -rf "$bak" 2>/dev/null || true
    [[ -d "$dest" ]] && { mv "$dest" "$bak" 2>/dev/null || rm -rf "$dest" 2>/dev/null || true; }
    if mv "$tmp" "$dest" 2>/dev/null; then
      rm -rf "$bak" 2>/dev/null || true
      return 0
    else
      [[ -d "$bak" ]] && mv "$bak" "$dest" 2>/dev/null || true
      rm -rf "$tmp" 2>/dev/null || true
      return 1
    fi
  else
    rm -rf "$tmp" 2>/dev/null || true
    return 1
  fi
}

# ── system ───────────────────────────────────────────────────────
# auto-install a package if the command is missing
pkg_install() {
  if   command -v pacman &>/dev/null; then sudo pacman -S --noconfirm "$@"
  elif command -v yay    &>/dev/null; then yay   -S --noconfirm "$@"
  elif command -v paru   &>/dev/null; then paru  -S --noconfirm "$@"
  else fail "no package manager found — install $* manually"; return 1; fi
}

auto_dep() {
  local cmd="$1" pkg="${2:-$1}"
  if command -v "$cmd" &>/dev/null; then
    ok "$cmd"
  else
    warn "$cmd not found — installing..."
    pkg_install "$pkg" && ok "$cmd (installed)" || fail "$cmd (install failed)"
  fi
}

# qdbus_cmd — returns qdbus6 or qdbus, whichever is available
qdbus_cmd() {
  for q in qdbus6 qdbus; do
    command -v "$q" &>/dev/null && { echo "$q"; return 0; }
  done
  return 1
}

# kwin_reconfigure — tell KWin to reload
kwin_reconfigure() {
  local q
  q=$(qdbus_cmd) || return 0
  "$q" org.kde.KWin /KWin org.kde.KWin.reconfigure &>/dev/null || true
}
