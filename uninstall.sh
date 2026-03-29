#!/usr/bin/env bash
# MacTahoe Liquid KDE — Uninstaller
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="$REPO/features.json"
WALLPAPERS="$HOME/.local/share/wallpapers"
FONTS_DIR="$HOME/.local/share/fonts"
ICONS_DIR="$HOME/.local/share/icons"
PLASMOIDS_DIR="$HOME/.local/share/plasma/plasmoids"

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
  echo -e "${GREEN}${BOLD}  Step ${STEP}: $*${RESET}"
}

cfg() {
  [[ -f "$CONFIG" ]] || { echo "true"; return; }
  local val
  val=$(grep -m1 "\"$1\"" "$CONFIG" | grep -o 'true\|false')
  echo "${val:-true}"
}

[[ -d "$REPO/src" ]] || { echo -e "${RED}  Run from repo root.${RESET}" >&2; exit 1; }

# ── sudo first ───────────────────────────────────────────────
echo ""
echo -e "  ${RED}${BOLD}This will reset your desktop to Breeze defaults.${RESET}"
echo ""
read -p "  Continue? [Y/n] " _confirm
[[ "$_confirm" =~ ^[Nn]$ ]] && { echo "  Aborted."; exit 0; }
echo ""

sudo -v || { echo -e "  ${RED}sudo required.${RESET}"; exit 1; }

# ── Step 1: Verification ──────────────────────────────────────
step "Verification"
note "Checks KDE version"

if ! command -v plasmashell &>/dev/null; then
  fail "KDE Plasma not found"; exit 1
fi

plasma_ver=$(plasmashell --version 2>/dev/null | grep -oP '[0-9]+[.][0-9]+[.][0-9]+' | head -1)
ok "KDE Plasma $plasma_ver"
[[ -f "$CONFIG" ]] && ok "features.json loaded"

# ── Step 2: Removing Wallpapers ──────────────────────────────
if [[ "$(cfg wallpapers)" == "true" ]]; then
  step "Removing Wallpapers"
  note "Removes all MacTahoe wallpaper packages"

  n=0
  for name in MacTahoe MacTahoe-Beach-Dawn MacTahoe-Beach-Day MacTahoe-Beach-Dusk MacTahoe-Beach-Night \
    MacHeritage-Sequoia MacHeritage-Sequoia-Sunrise MacHeritage-Sonoma MacHeritage-Sonoma-Horizon \
    MacHeritage-Ventura MacHeritage-Monterey MacHeritage-BigSur; do
    [[ -d "$WALLPAPERS/$name" ]] || continue
    rm -rf "$WALLPAPERS/$name" 2>/dev/null && ok "$name" && n=$((n+1)) || fail "$name"
  done
  for d in "$WALLPAPERS"/MacTahoe-Landscape-*/; do
    [[ -d "$d" ]] || continue
    name=$(basename "$d")
    rm -rf "$d" 2>/dev/null && ok "$name" && n=$((n+1)) || fail "$name"
  done
  info "$n wallpapers removed"
fi

# ── Step 3: Removing Fonts ───────────────────────────────────
if [[ "$(cfg fonts)" == "true" ]]; then
  step "Removing Fonts"
  n=0
  for pattern in "SF-Pro*" "SF-Mono*" "SFPro*" "SFMono*"; do
    for f in "$FONTS_DIR/"$pattern; do
      [[ -f "$f" ]] || continue
      rm -f "$f" 2>/dev/null && n=$((n+1))
    done
  done
  [[ $n -gt 0 ]] && fc-cache -f "$FONTS_DIR" 2>/dev/null || true
  info "$n font files removed"
fi

# ── Step 4: Removing Cursors ─────────────────────────────────
if [[ "$(cfg cursors)" == "true" ]]; then
  step "Removing Cursors"
  n=0
  for theme in "$ICONS_DIR"/MacTahoeLiquidKde*; do
    [[ -d "$theme" ]] || continue
    name=$(basename "$theme")
    [[ "$name" == *Icons* ]] && continue
    rm -rf "$theme" 2>/dev/null && ok "$name" && n=$((n+1)) || fail "$name"
  done
  info "$n cursor themes removed"
fi

# ── Step 5: Removing Icons ───────────────────────────────────
if [[ "$(cfg icons)" == "true" ]]; then
  step "Removing Icons"
  n=0
  for theme in "$ICONS_DIR"/MacTahoeLiquidKde-Icons*; do
    [[ -d "$theme" ]] || continue
    name=$(basename "$theme")
    rm -rf "$theme" 2>/dev/null && ok "$name" && n=$((n+1)) || fail "$name"
  done
  info "$n icon themes removed"
fi

# ── Step 6: Removing Theme Watcher ──────────────────────────
step "Removing Theme Watcher"
note "Stops and removes the auto light/dark theme switcher"

_svc="mactahoe-theme-watcher.service"
if systemctl --user is-enabled "$_svc" &>/dev/null; then
  systemctl --user disable --now "$_svc" 2>/dev/null || true
  ok "Theme watcher stopped"
else
  ok "Theme watcher (not running)"
fi
rm -f "$HOME/.config/systemd/user/$_svc" 2>/dev/null
systemctl --user daemon-reload 2>/dev/null || true
rm -f "$HOME/.local/bin/mactahoe-theme-switch" 2>/dev/null && ok "Theme switcher removed"

# ── Step 7: Removing Kvantum Theme ──────────────────────────
if [[ "$(cfg kvantum)" == "true" ]]; then
  step "Removing Kvantum Theme"
  note "Removes MacTahoe Liquid KDE Kvantum theme (keeps Kvantum installed)"

  _kv_dir="$HOME/.config/Kvantum/MacTahoeLiquidKde"
  if [[ -d "$_kv_dir" ]]; then
    # reset widget style back to Breeze
    if command -v kwriteconfig6 &>/dev/null; then
      kwriteconfig6 --file kdeglobals --group KDE --key widgetStyle Breeze
      ok "Widget style reset to Breeze"
    fi
    # reset kvantum to default before removing
    if command -v kvantummanager &>/dev/null; then
      kvantummanager --set Default &>/dev/null || true
    fi
    rm -rf "$_kv_dir" 2>/dev/null && ok "MacTahoeLiquidKde theme removed" || fail "MacTahoeLiquidKde theme"
  else
    ok "MacTahoeLiquidKde theme (not installed)"
  fi
fi

# ── Step 8: Removing Plasmoids ───────────────────────────────
if [[ "$(cfg plasmoids)" == "true" ]]; then
  step "Removing Plasmoids"
  n=0
  for widget in "$PLASMOIDS_DIR"/org.kde.mactahoe-liquid-kde.*; do
    [[ -d "$widget" ]] || continue
    name=$(basename "$widget")
    rm -rf "$widget" 2>/dev/null && ok "$name" && n=$((n+1)) || fail "$name"
  done
  info "$n plasmoids removed"
fi

# ── Step 9: Removing Liquid Glass ────────────────────────────
if [[ "$(cfg liquid_glass)" == "true" ]]; then
  step "Removing Liquid Glass"

  # unload effect
  for _q in qdbus6 qdbus; do
    command -v "$_q" &>/dev/null && {
      "$_q" org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect liquidglass &>/dev/null || true
      break
    }
  done
  kwriteconfig6 --file kwinrc --group Plugins --key liquidglassEnabled false 2>/dev/null || true

  _plugin_dir=$(qmake6 -query QT_INSTALL_PLUGINS 2>/dev/null \
    || qtpaths6 --plugin-dir 2>/dev/null \
    || echo "/usr/lib/qt6/plugins")
  for _so in "$_plugin_dir/kwin/effects/plugins/liquidglass.so" "$_plugin_dir/kwin/effects/configs/kwin_liquidglass_config.so"; do
    [[ -f "$_so" ]] && sudo rm -f "$_so" 2>/dev/null && ok "$(basename "$_so")"
  done
  info "Liquid Glass removed"
fi

# ── Step Final: Reset to Breeze defaults ─────────────────────
step "Applying Changes"
note "Resets to Breeze defaults and restarts Plasma"

# layout — reset to default KDE panel
if [[ "$(cfg layout)" == "true" ]]; then
  _layout="$REPO/src/offline/layouts/default.js"
  if [[ -f "$_layout" ]]; then
    for _q in qdbus6 qdbus; do
      command -v "$_q" &>/dev/null && {
        "$_q" org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$(cat "$_layout")" &>/dev/null \
          && ok "Layout reset" || warn "layout reset failed"
        break
      }
    done
  fi
fi

# reset configs
if command -v kwriteconfig6 &>/dev/null; then
  if [[ "$(cfg fonts)" == "true" ]]; then
    kwriteconfig6 --file kdeglobals --group General --key font                 "Noto Sans,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key menuFont             "Noto Sans,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key toolBarFont          "Noto Sans,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key taskbarFont          "Noto Sans,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key smallestReadableFont "Noto Sans,8,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key fixed                "Hack,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group WM      --key activeFont           "Noto Sans,10,-1,5,50,0,0,0,0,0"
    ok "Fonts reset"
  fi
  if [[ "$(cfg cursors)" == "true" ]]; then
    kwriteconfig6 --file kcminputrc --group Mouse --key cursorTheme "breeze_cursors"
    plasma-apply-cursortheme "breeze_cursors" &>/dev/null || true
    ok "Cursor reset"
  fi
  if [[ "$(cfg icons)" == "true" ]]; then
    kwriteconfig6 --file kdeglobals --group Icons --key Theme "breeze"
    plasma-apply-icontheme breeze &>/dev/null || true
    ok "Icons reset"
  fi
  if [[ "$(cfg wallpapers)" == "true" ]]; then
    for _p in /usr/share/wallpapers/Next /usr/share/wallpapers/Breeze /usr/share/wallpapers/Flow; do
      [[ -d "$_p" ]] && { plasma-apply-wallpaperimage "$_p" &>/dev/null || true; ok "Wallpaper reset"; break; }
    done
  fi
  plasma-apply-colorscheme BreezeLight &>/dev/null || true
  ok "Color scheme reset"
fi

# flush caches and restart
rm -rf "$HOME/.cache/icon-cache.kcache" 2>/dev/null || true
rm -rf "$HOME/.cache/plasma-svgelements-"* 2>/dev/null || true
rm -rf "$HOME/.cache/plasma_theme_"* 2>/dev/null || true
find "$HOME/.cache" -maxdepth 1 -name "ksycoca6*" -delete 2>/dev/null || true
kbuildsycoca6 --noincremental 2>/dev/null || true
ok "Caches flushed"

# restart plasma + KWin
systemctl --user restart plasma-plasmashell 2>/dev/null || killall plasmashell 2>/dev/null || true
ok "Plasma restarted"
for _q in qdbus6 qdbus; do
  command -v "$_q" &>/dev/null && { "$_q" org.kde.KWin /KWin org.kde.KWin.reconfigure &>/dev/null || true; break; }
done

# ── Done ──────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  ── Done${RESET}"
if [[ ${#ERRORS[@]} -eq 0 ]]; then
  ok "MacTahoe Liquid KDE uninstalled successfully"
else
  warn "${#ERRORS[@]} issue(s):"
  for e in "${ERRORS[@]}"; do fail "$e"; done
fi
echo ""
