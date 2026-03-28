#!/usr/bin/env bash
# MacTahoe Liquid KDE — step-cursors (online installer step)
# mirrors documented in src/mirrors/cursors.txt
set -uo pipefail

DEST="src/steps/cursors"
TMP="/tmp/tahoe-cursors-$$"

source "$(dirname "$0")/utils.sh"

[[ -d "src" ]] || { echo -e "\033[0;31m  run from repo root.\033[0m" >&2; exit 1; }
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP"

# clean stale cursor dirs from previous runs before downloading fresh
rm -rf "$DEST"/MacTahoeLiquidKde* "$DEST"/MacTahoe-cursors*
mkdir -p "$DEST"

any_ok=false

# ── shared handler ─────────────────────────────────────────────
# maps extracted cursor theme dirs to consistent MacTahoe Liquid KDE names
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
        # skip archive root dirs (e.g. MacTahoe-icon-theme-main)
        [[ "$raw" == *-main || "$raw" == *-master ]] && continue
        name="${prefix}-${raw}"
        ;;
    esac
    rm -rf "$DEST/$name"
    cp -r "$dir" "$DEST/$name" 2>/dev/null && installed=true || fail "$name (copy failed)"
  done < <(find "$xdir" -mindepth 1 -maxdepth 5 -type d -print0 2>/dev/null)
  $installed
}

# ── source 1: MacTahoe cursors (vinceliuice) ──────────────────
MIRRORS=(
  "https://github.com/vinceliuice/MacTahoe-icon-theme/archive/refs/heads/main.zip|zip|MacTahoeLiquidKde"
)
run_mirrors && any_ok=true || warn "MacTahoeLiquidKde cursors — all mirrors failed"

# reset tmp between downloads
rm -rf "${TMP:?}/mirror"* "${TMP:?}/extract"*

# ── source 2: Apple cursors (ful1e5) ─────────────────────────
MIRRORS=(
  "https://github.com/ful1e5/apple_cursor/releases/latest/download/macOS.tar.gz|tar.gz|MacTahoeLiquidKde-Apple"
  "https://github.com/ful1e5/apple_cursor/releases/latest/download/macOS.tar.xz|tar.xz|MacTahoeLiquidKde-Apple"
)
run_mirrors && any_ok=true || warn "MacTahoeLiquidKde Apple cursors — all mirrors failed"

$any_ok || { fail "no cursor themes installed — all mirrors failed"; exit 1; }
