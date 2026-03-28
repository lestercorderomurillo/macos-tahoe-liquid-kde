#!/usr/bin/env bash
# MacTahoe Liquid KDE — Uninstaller
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="$REPO/features.json"
WALLPAPERS="$HOME/.local/share/wallpapers"
FONTS_DIR="$HOME/.local/share/fonts"
ICONS_DIR="$HOME/.local/share/icons"
# PLASMA="$HOME/.local/share/plasma/desktoptheme"
# LOOKFEEL="$HOME/.local/share/plasma/look-and-feel"
# AURORAE="$HOME/.local/share/aurorae/themes"
# KVANTUM="$HOME/.config/Kvantum"
# COLORS="$HOME/.local/share/color-schemes"
# SOUNDS="$HOME/.local/share/sounds"
# GTK="$HOME/.themes"
# APPS="$HOME/.local/share/applications"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; RESET='\033[0m'; BOLD='\033[1m'

ERRORS=()
STEP=0

ok()   { echo -e "  ${GREEN}✓${RESET}  $*"; }
info() { echo ""; echo -e "  ${BOLD}$*${RESET}"; }
note() { echo -e "  $*"; echo ""; }
warn() { echo -e "  ${YELLOW}⚠${RESET}  $*"; }
fail() { echo -e "  ${RED}✗${RESET}  $*"; ERRORS+=("$*"); }
step() {
  ((STEP++))
  echo ""
  echo -e "${GREEN}${BOLD}  ── Step ${STEP}: $*${RESET}"
}

cfg() {
  [[ -f "$CONFIG" ]] || { echo "true"; return; }
  local val
  val=$(grep -m1 "\"$1\"" "$CONFIG" | grep -o 'true\|false')
  echo "${val:-true}"
}

# ── Step 1: Verification ──────────────────────────────────────
step "Verification"
note "Checks KDE version and required tools"

if ! command -v plasmashell &>/dev/null; then
  fail "KDE Plasma not found"
  echo ""
  echo "     MacTahoe Liquid KDE requires KDE Plasma 6.6+."
  echo "     It does not support GNOME, XFCE, or other desktops."
  echo ""
  exit 1
fi

plasma_ver=$(plasmashell --version 2>/dev/null | grep -oP '[0-9]+[.][0-9]+[.][0-9]+' | head -1)
plasma_major=$(echo "$plasma_ver" | cut -d. -f1)
plasma_minor=$(echo "$plasma_ver" | cut -d. -f2)

if [[ "$plasma_major" -lt 6 ]] || { [[ "$plasma_major" -eq 6 ]] && [[ "$plasma_minor" -lt 6 ]]; }; then
  fail "KDE Plasma $plasma_ver (6.6+ required)"
  echo "     Please update KDE Plasma before uninstalling."
  echo ""
  exit 1
fi

ok "KDE Plasma $plasma_ver"
command -v kwriteconfig6 &>/dev/null && ok "kwriteconfig6" || warn "kwriteconfig6 not found — settings won't be reset automatically"
[[ -f "$CONFIG" ]] && ok "features.json loaded"

# ── Step 2: Removing Wallpapers ───────────────────────────────
if [[ "$(cfg wallpapers)" == "true" ]]; then
  step "Removing Wallpapers"
  note "Removes all installed MacTahoe wallpaper packages"

  n=0
  for name in \
    MacTahoe \
    MacTahoe-Beach-Dawn MacTahoe-Beach-Day \
    MacTahoe-Beach-Dusk MacTahoe-Beach-Night \
    MacHeritage-Sequoia MacHeritage-Sequoia-Sunrise \
    MacHeritage-Sonoma MacHeritage-Sonoma-Horizon \
    MacHeritage-Ventura MacHeritage-Monterey MacHeritage-BigSur; do
    [[ -d "$WALLPAPERS/$name" ]] || continue
    if err=$(rm -rf "$WALLPAPERS/$name" 2>&1); then
      ok "$name (removed)"; n=$((n + 1))
    else
      fail "$name (remove failed: ${err:-unknown error})"
    fi
  done
  for d in "$WALLPAPERS"/MacTahoe-Landscape-*/; do
    [[ -d "$d" ]] || continue
    name=$(basename "$d")
    if err=$(rm -rf "$d" 2>&1); then
      ok "$name (removed)"; n=$((n + 1))
    else
      fail "$name (remove failed: ${err:-unknown error})"
    fi
  done
  [[ $n -eq 0 ]] \
    && info "0 wallpapers removed (already removed?)" \
    || info "$n wallpapers removed"
fi

# ── Step 3: Removing Fonts ────────────────────────────────────
if [[ "$(cfg fonts)" == "true" ]]; then
  step "Removing Fonts"
  note "Removes SF Pro and SF Mono"

  n=0
  for pattern in "SF-Pro*" "SF-Mono*" "SFPro*" "SFMono*"; do
    for f in "$FONTS_DIR/"$pattern; do
      [[ -f "$f" ]] || continue
      if err=$(rm -f "$f" 2>&1); then
        n=$((n + 1))
      else
        fail "$(basename "$f") (remove failed: ${err:-unknown error})"
      fi
    done
  done
  [[ $n -eq 0 ]] \
    && info "0 font files removed (already removed?)" \
    || { info "$n font files removed"; fc-cache -f "$FONTS_DIR" 2>/dev/null || true; }
fi

# ── Step 4: Removing Plasma Theme ────────────────────────────
# if [[ "$(cfg plasma_theme)" == "true" ]]; then
#   step "Removing Plasma Theme"
#   note "Removes the MacTahoe Plasma desktop theme"
#   [[ -d "$PLASMA/MacTahoe" ]]   && rm -rf "$PLASMA/MacTahoe"
#   [[ -d "$LOOKFEEL/MacTahoe" ]] && rm -rf "$LOOKFEEL/MacTahoe"
# fi

# ── Step 5: Removing Window Decorations ──────────────────────
# if [[ "$(cfg window_decorations)" == "true" ]]; then
#   step "Removing Window Decorations"
#   note "Removes Aurorae window decorations"
# fi

# ── Step 6: Removing Kvantum Theme ───────────────────────────
# if [[ "$(cfg kvantum)" == "true" ]]; then
#   step "Removing Kvantum Theme"
#   note "Removes the MacTahoe Kvantum theme"
# fi

# ── Step 7: Removing Color Schemes ───────────────────────────
# if [[ "$(cfg color_schemes)" == "true" ]]; then
#   step "Removing Color Schemes"
#   note "Removes Tahoe Light and Dark color palettes"
# fi

# ── Step 8: Removing Cursors ─────────────────────────────────
if [[ "$(cfg cursors)" == "true" ]]; then
  step "Removing Cursors"
  note "Removes the MacTahoe cursor theme"

  n=0
  for theme in "$ICONS_DIR"/MacTahoeLiquidKde* "$ICONS_DIR"/MacTahoe*cursors* "$ICONS_DIR"/MacTahoe*Cursors*; do
    [[ -d "$theme" ]] || continue
    name=$(basename "$theme")
    [[ "$name" == *Icons* ]] && continue  # handled by the icons step
    if err=$(rm -rf "$theme" 2>&1); then
      ok "$name (removed)"; n=$((n + 1))
    else
      fail "$name (remove failed: ${err:-unknown error})"
    fi
  done
  [[ $n -eq 0 ]] \
    && info "0 cursor themes removed (already removed?)" \
    || info "$n cursor themes removed"
fi

# ── Step 9: Removing Icons ────────────────────────────────────
if [[ "$(cfg icons)" == "true" ]]; then
  step "Removing Icons"
  note "Removes the MacTahoe Liquid KDE icon themes"

  n=0
  for theme in "$ICONS_DIR"/MacTahoeLiquidKde-Icons*; do
    [[ -d "$theme" ]] || continue
    name=$(basename "$theme")
    if err=$(rm -rf "$theme" 2>&1); then
      ok "$name (removed)"; n=$((n + 1))
    else
      fail "$name (remove failed: ${err:-unknown error})"
    fi
  done
  [[ $n -eq 0 ]] \
    && info "0 icon themes removed (already removed?)" \
    || info "$n icon themes removed"
fi

# ── Step 10: Removing Sounds ─────────────────────────────────
# if [[ "$(cfg sounds)" == "true" ]]; then
#   step "Removing Sounds"
#   note "Removes macOS-style notification sounds"
# fi

# ── Step 11: Removing GTK Theme ──────────────────────────────
# if [[ "$(cfg gtk)" == "true" ]]; then
#   step "Removing GTK Theme"
#   note "Removes the MacTahoe GTK2/3/4 theme"
# fi

# ── Step 12: Removing SDDM Theme ─────────────────────────────
# if [[ "$(cfg sddm)" == "true" ]]; then
#   step "Removing SDDM Theme"
#   note "Removes the macOS-style login screen"
# fi

# ── Step 13: Removing Custom Apps ────────────────────────────
# if [[ "$(cfg apps)" == "true" ]]; then
#   step "Removing Custom Apps"
#   note "Removes About This Mac and other Electron apps"
# fi

# ── Step Final: Applying Changes ──────────────────────────────
step "Applying Changes"
note "Resets settings and tells KDE to reload"

if command -v kwriteconfig6 &>/dev/null; then
  if [[ "$(cfg fonts)" == "true" ]]; then
    kwriteconfig6 --file kdeglobals --group General --key font                 "Noto Sans,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key menuFont             "Noto Sans,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key toolBarFont          "Noto Sans,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key taskbarFont          "Noto Sans,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key smallestReadableFont "Noto Sans,8,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key fixed                "Hack,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group WM      --key activeFont           "Noto Sans,10,-1,5,50,0,0,0,0,0"
    ok "KDE fonts reset to defaults"
  fi

  if [[ "$(cfg cursors)" == "true" ]]; then
    kwriteconfig6 --file kcminputrc --group Mouse --key cursorTheme "breeze_cursors"
    ok "cursor theme reset to Breeze"
  fi

  if [[ "$(cfg icons)" == "true" ]]; then
    kwriteconfig6 --file kdeglobals --group Icons --key Theme "breeze"
    ok "icon theme reset to Breeze"
    if command -v plasma-apply-icontheme &>/dev/null; then
      plasma-apply-icontheme breeze 2>/dev/null && ok "icon theme applied live" || true
    else
      dbus-send --session --type=signal /KIconLoader org.kde.KIconLoader.iconChanged 2>/dev/null || true
    fi
  fi
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
echo -e "${GREEN}${BOLD}  ── Done${RESET}"
if [[ ${#ERRORS[@]} -eq 0 ]]; then
  ok "MacTahoe Liquid KDE uninstalled successfully"
else
  warn "${#ERRORS[@]} issue(s) — everything else removed fine:"
  for e in "${ERRORS[@]}"; do fail "$e"; done
fi
echo ""
echo -e "  ${BOLD}Log out and back in to apply all changes${RESET}"
echo ""