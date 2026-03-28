#!/usr/bin/env bash
# MacTahoe KDE — Installer
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO/src"
STEPS="$REPO/src/steps"
WALLPAPERS="$HOME/.local/share/wallpapers"
FONTS_DIR="$HOME/.local/share/fonts"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; RESET='\033[0m'; BOLD='\033[1m'

ERRORS=()
STEP=0

ok()   { echo -e "  ${GREEN}✓${RESET}  $*"; }
info() { echo -e "  ${BOLD}$*${RESET}"; }
note() { echo -e "  $*"; echo ""; }
warn() { echo -e "  ${YELLOW}⚠${RESET}  $*"; }
fail() { echo -e "  ${RED}✗${RESET}  $*"; ERRORS+=("$*"); }
step() {
  ((STEP++))
  echo ""
  echo -e "${GREEN}${BOLD}  ── Step ${STEP}: $* ─────────────────────────────${RESET}"
}

[[ -d "$SRC" ]] || { echo -e "${RED}  Run from repo root.${RESET}" >&2; exit 1; }

# ── Step 1: Verification ──────────────────────────────────────
step "Verification"
note "Checks KDE version and required tools"

if ! command -v plasmashell &>/dev/null; then
  fail "KDE Plasma not found"
  echo ""
  echo "     MacTahoe KDE requires KDE Plasma 6.6+."
  echo "     It does not support GNOME, XFCE, or other desktops."
  echo ""
  exit 1
fi

plasma_ver=$(plasmashell --version 2>/dev/null | grep -oP '[0-9]+[.][0-9]+[.][0-9]+' | head -1)
plasma_major=$(echo "$plasma_ver" | cut -d. -f1)
plasma_minor=$(echo "$plasma_ver" | cut -d. -f2)

if [[ "$plasma_major" -lt 6 ]] || { [[ "$plasma_major" -eq 6 ]] && [[ "$plasma_minor" -lt 6 ]]; }; then
  fail "KDE Plasma $plasma_ver (6.6+ required)"
  echo "     Please update KDE Plasma before installing."
  echo ""
  exit 1
fi

ok "KDE Plasma $plasma_ver"
command -v kwriteconfig6 &>/dev/null && ok "kwriteconfig6" || warn "kwriteconfig6 not found — fonts won't apply automatically"
command -v fc-cache      &>/dev/null && ok "fontconfig"    || warn "fc-cache not found"

# ── Step 2: Installing Wallpapers ─────────────────────────────
step "Installing Wallpapers"
note "Downloads and installs macOS wallpaper packages"

[[ -f "$STEPS/step-wallpapers.sh" ]] \
  && bash "$STEPS/step-wallpapers.sh" \
  || fail "step-wallpapers.sh not found (source missing)"

mkdir -p "$WALLPAPERS"
n_inst=0; n_re=0
for wp in "$SRC/steps/wallpapers"/*/; do
  [[ -d "$wp" ]] || continue
  name=$(basename "$wp")

  img_count=$(find "$wp/contents" -type f 2>/dev/null | wc -l)
  if [[ $img_count -eq 0 ]]; then
    fail "$name (download incomplete — re-run to retry)"
    continue
  fi

  dest="$WALLPAPERS/$name"
  tmp="$WALLPAPERS/.tmp_${name}_$$"
  reinstall=false
  [[ -d "$dest" ]] && reinstall=true

  # Copy to a temp dir first — avoids KDE holding open handles on the active
  # wallpaper dir; rm+mv is near-atomic on the same filesystem
  rm -rf "$tmp" 2>/dev/null || true
  if err=$(cp -r "$wp/." "$tmp/" 2>&1 || { mkdir -p "$tmp" && cp -r "$wp/." "$tmp/"; }); then
    rm -rf "$dest"  2>/dev/null || true
    if err2=$(mv "$tmp" "$dest" 2>&1); then
      if $reinstall; then
        ok "$name (reinstalled)"; n_re=$((n_re + 1))
      else
        ok "$name (installed)";   n_inst=$((n_inst + 1))
      fi
    else
      rm -rf "$tmp" 2>/dev/null || true
      fail "$name (move failed: ${err2:-unknown error})"
    fi
  else
    rm -rf "$tmp" 2>/dev/null || true
    fail "$name (copy failed: ${err:-unknown error})"
  fi
done
info "$((n_inst + n_re)) wallpapers — $n_inst installed, $n_re reinstalled"

# ── Step 3: Installing Fonts ──────────────────────────────────
step "Installing Fonts"
note "Downloads and installs SF Pro and SF Mono"

[[ -f "$STEPS/step-fonts.sh" ]] \
  && bash "$STEPS/step-fonts.sh" \
  || fail "step-fonts.sh not found (source missing)"

mkdir -p "$FONTS_DIR"
declare -A g_inst=() g_re=()
for f in "$SRC/steps/fonts/"*.otf "$SRC/steps/fonts/"*.ttf; do
  [[ -f "$f" ]] || continue
  name=$(basename "$f")
  if   [[ "$name" == SF-Mono* ]] || [[ "$name" == SFMono* ]]; then grp="SF Mono"
  elif [[ "$name" == SF-Pro*  ]] || [[ "$name" == SFPro*  ]]; then grp="SF Pro"
  else grp="Other"; fi

  if [[ -f "$FONTS_DIR/$name" ]]; then
    if err=$(cp "$f" "$FONTS_DIR/" 2>&1); then
      g_re[$grp]=$(( ${g_re[$grp]:-0} + 1 ))
    else
      fail "$name (copy failed: ${err:-unknown error})"
    fi
  else
    if err=$(cp "$f" "$FONTS_DIR/" 2>&1); then
      g_inst[$grp]=$(( ${g_inst[$grp]:-0} + 1 ))
    else
      fail "$name (copy failed: ${err:-unknown error})"
    fi
  fi
done

for grp in "SF Pro" "SF Mono" "Other"; do
  i=${g_inst[$grp]:-0}; r=${g_re[$grp]:-0}
  [[ $((i+r)) -eq 0 ]] && continue
  parts=""; [[ $i -gt 0 ]] && parts="$i installed"
  [[ $r -gt 0 ]] && parts="${parts:+$parts, }$r reinstalled"
  info "$grp — $parts"
done
fc-cache -f "$FONTS_DIR" 2>/dev/null || true

# ── Step 4: Installing Plasma Theme ──────────────────────────
# step "Installing Plasma Theme"
# note "Installs the MacTahoe Plasma desktop theme"
# ── Step 5: Installing Window Decorations ────────────────────
# ── Step 6: Installing Kvantum Theme ─────────────────────────
# ── Step 7: Installing Color Schemes ─────────────────────────
# ── Step 8: Installing Icons & Cursors ───────────────────────
# ── Step 9: Installing Sounds ────────────────────────────────
# ── Step 10: Installing GTK Theme ────────────────────────────
# ── Step 11: Installing SDDM Theme ───────────────────────────
# ── Step 12: Installing Custom Apps ──────────────────────────

# ── Step Final: Applying Changes ─────────────────────────────
step "Applying Changes"
note "Applies fonts and tells KDE to reload"

# DPI: macOS 72 DPI → KDE 96 DPI, factor 0.75 → macOS 13pt ≈ 10pt in KDE
# Qt weights: 50=Regular  57=Medium  63=Semibold  75=Bold
if command -v kwriteconfig6 &>/dev/null; then
  kwriteconfig6 --file kdeglobals --group General --key font                 "SF Pro Text,10,-1,5,50,0,0,0,0,0"
  kwriteconfig6 --file kdeglobals --group General --key menuFont             "SF Pro Text,10,-1,5,50,0,0,0,0,0"
  kwriteconfig6 --file kdeglobals --group General --key toolBarFont          "SF Pro Text,10,-1,5,50,0,0,0,0,0"
  kwriteconfig6 --file kdeglobals --group General --key taskbarFont          "SF Pro Text,10,-1,5,50,0,0,0,0,0"
  kwriteconfig6 --file kdeglobals --group General --key smallestReadableFont "SF Pro Text,8,-1,5,50,0,0,0,0,0"
  kwriteconfig6 --file kdeglobals --group General --key fixed                "SF Mono,10,-1,5,50,0,0,0,0,0"
  kwriteconfig6 --file kdeglobals --group WM      --key activeFont           "SF Pro Display,11,-1,5,63,0,0,0,0,0"
  ok "KDE fonts configured"
fi

for qdbus_cmd in qdbus6 qdbus; do
  command -v "$qdbus_cmd" &>/dev/null && {
    "$qdbus_cmd" org.kde.KWin /KWin org.kde.KWin.reconfigure 2>/dev/null \
      && ok "KWin reconfigured" || warn "KWin reconfigure failed (non-fatal)"
    break
  }
done

if command -v dbus-send &>/dev/null; then
  dbus-send --session --dest=org.kde.plasmashell \
    /PlasmaShell org.kde.PlasmaShell.refreshCurrentShell 2>/dev/null \
    && ok "Plasma shell refreshed" || warn "Plasma shell refresh failed (non-fatal)"
fi

if command -v kbuildsycoca6 &>/dev/null; then
  kbuildsycoca6 --noincremental 2>/dev/null \
    && ok "KDE system cache rebuilt" || warn "kbuildsycoca6 failed (non-fatal)"
elif command -v kbuildsycoca5 &>/dev/null; then
  kbuildsycoca5 --noincremental 2>/dev/null \
    && ok "KDE system cache rebuilt" || warn "kbuildsycoca5 failed (non-fatal)"
fi

# ── Done ──────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  ── Done ────────────────────────────────────────${RESET}"
if [[ ${#ERRORS[@]} -eq 0 ]]; then
  ok "MacTahoe KDE installed successfully"
else
  warn "${#ERRORS[@]} issue(s) — everything else installed fine:"
  for e in "${ERRORS[@]}"; do fail "$e"; done
fi
echo ""
echo -e "  ${BOLD}Log out and back in to apply all changes${RESET}"
echo ""