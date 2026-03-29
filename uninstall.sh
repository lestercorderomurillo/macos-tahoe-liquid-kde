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

# ── feature flags (same system as install.sh) ────────────
_ALL_FEATURES=(wallpapers fonts cursors plasma_theme window_decorations kvantum color_schemes icons plasmoids liquid_glass layout sounds gtk sddm apps no_download)
declare -A _feat=()
declare -A _cli=()

_cfg_read() {
  local key="$1"
  [[ -f "$CONFIG" ]] || { echo "true"; return; }
  local val
  val=$(sed -n 's/.*"'"$key"'"[[:space:]]*:[[:space:]]*\("[^"]*"\|true\|false\).*/\1/p' "$CONFIG" | tr -d '"' | head -1)
  echo "${val:-true}"
}

for _f in "${_ALL_FEATURES[@]}"; do _feat[$_f]="$(_cfg_read "$_f")"; done

for _arg in "$@"; do
  case "$_arg" in
    --no-*)
      _key="${_arg#--no-}"
      _key="${_key//-/_}"
      for _f in "${_ALL_FEATURES[@]}"; do
        [[ "$_f" == "$_key" ]] && { _cli[$_f]="false"; break; }
      done
      ;;
    --*)
      _key="${_arg#--}"
      _key="${_key//-/_}"
      for _f in "${_ALL_FEATURES[@]}"; do
        [[ "$_f" == "$_key" ]] && { _cli[$_f]="true"; break; }
      done
      ;;
  esac
done

for _f in "${_ALL_FEATURES[@]}"; do
  [[ -n "${_cli[$_f]:-}" ]] && _feat[$_f]="${_cli[$_f]}"
done

cfg() { echo "${_feat[$1]:-true}"; }

[[ -d "$REPO/src" ]] || { echo -e "${RED}  Run from repo root.${RESET}" >&2; exit 1; }

# ── sudo first ───────────────────────────────────────────────
echo ""
echo -e "  ${RED}${BOLD}This will reset your desktop to Breeze defaults.${RESET}"
echo ""
read -p "  Continue? [Y/n] " _confirm
[[ "$_confirm" =~ ^[Nn]$ ]] && { echo "  Aborted."; exit 0; }
echo ""

sudo -v || { echo -e "  ${RED}sudo required.${RESET}"; exit 1; }

# ── Verification ──────────────────────────────────────
step "Verification"
note "Checks KDE version"

if ! command -v plasmashell &>/dev/null; then
  fail "KDE Plasma not found"; exit 1
fi

plasma_ver=$(plasmashell --version 2>/dev/null | grep -oP '[0-9]+[.][0-9]+[.][0-9]+' | head -1)
ok "KDE Plasma $plasma_ver"
[[ -f "$CONFIG" ]] && ok "features.json loaded"

# ── Removing Wallpapers ──────────────────────────────
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

# ── Removing Fonts ───────────────────────────────────
if [[ "$(cfg fonts)" == "true" ]]; then
  step "Removing Fonts"
  note "Removes SF Pro and SF Mono font files"
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

# ── Removing Cursors ─────────────────────────────────
if [[ "$(cfg cursors)" == "true" ]]; then
  step "Removing Cursors"
  note "Removes MacTahoe Liquid KDE cursor themes"
  n=0
  for theme in "$ICONS_DIR"/MacTahoeLiquidKde*; do
    [[ -d "$theme" ]] || continue
    name=$(basename "$theme")
    [[ "$name" == *Icons* ]] && continue
    rm -rf "$theme" 2>/dev/null && ok "$name" && n=$((n+1)) || fail "$name"
  done
  info "$n cursor themes removed"
fi

# ── Removing Icons ───────────────────────────────────
if [[ "$(cfg icons)" == "true" ]]; then
  step "Removing Icons"
  note "Removes MacTahoe Liquid KDE icon themes"
  n=0
  for theme in "$ICONS_DIR"/MacTahoeLiquidKde-Icons*; do
    [[ -d "$theme" ]] || continue
    name=$(basename "$theme")
    rm -rf "$theme" 2>/dev/null && ok "$name" && n=$((n+1)) || fail "$name"
  done
  info "$n icon themes removed"
fi

# ── Removing Theme Switcher ─────────────────────────
step "Removing Theme Switcher"
note "Stops and removes the auto light/dark theme switcher"

for _svc in mac-tahoe-liquid-kde-theme.service mactahoe-theme-watcher.service; do
  systemctl --user disable --now "$_svc" 2>/dev/null || true
  rm -f "$HOME/.config/systemd/user/$_svc" 2>/dev/null
done
systemctl --user daemon-reload 2>/dev/null || true
rm -f "$HOME/.local/bin/mac-tahoe-theme-switch" "$HOME/.local/bin/mactahoe-theme-switch" 2>/dev/null
ok "Theme switcher removed"

# ── Removing Plasma Theme ───────────────────────────
if [[ "$(cfg plasma_theme)" == "true" ]]; then
  step "Removing Plasma Theme"
  note "Removes MacTahoe Liquid KDE Plasma desktop theme and resets to Breeze"
  n=0
  for variant in MacTahoeLiquidKde-Dark MacTahoeLiquidKde-Light; do
    _pt_dir="$HOME/.local/share/plasma/desktoptheme/$variant"
    [[ -d "$_pt_dir" ]] || continue
    rm -rf "$_pt_dir" 2>/dev/null && ok "$variant removed" && n=$((n+1)) || fail "$variant"
  done
  # reset to breeze
  if command -v kwriteconfig6 &>/dev/null; then
    kwriteconfig6 --file plasmarc --group Theme --key name "default" 2>/dev/null || true
  fi
  info "$n Plasma themes removed"
fi

# ── Removing Kvantum Theme ──────────────────────────
if [[ "$(cfg kvantum)" == "true" ]]; then
  step "Removing Kvantum Theme"
  note "Removes MacTahoe Liquid KDE Kvantum theme (keeps Kvantum installed)"

  _kv_dir="$HOME/.config/Kvantum/mac-tahoe-liquid-kde"
  if [[ -d "$_kv_dir" ]]; then
    # reset widget style back to Breeze
    if command -v kwriteconfig6 &>/dev/null; then
      kwriteconfig6 --file kdeglobals --group KDE --key widgetStyle Breeze
      ok "Widget style reset to Breeze"
    fi
    # reset kvantum to default before removing
    if command -v kvantummanager &>/dev/null; then
      QT_QPA_PLATFORM=offscreen kvantummanager --set Default &>/dev/null || true
    fi
    rm -rf "$_kv_dir" 2>/dev/null && ok "MacTahoeLiquidKde theme removed" || fail "MacTahoeLiquidKde theme"
  else
    ok "MacTahoeLiquidKde theme (not installed)"
  fi
fi

# ── Removing Color Schemes ──────────────────────────
if [[ "$(cfg color_schemes)" == "true" ]]; then
  step "Removing Color Schemes"
  note "Removes MacTahoe Liquid KDE color schemes (light and dark)"
  n=0
  for cs in "$HOME/.local/share/color-schemes"/MacTahoeLiquidKde*.colors; do
    [[ -f "$cs" ]] || continue
    name=$(basename "$cs" .colors)
    rm -f "$cs" 2>/dev/null && ok "$name removed" && n=$((n+1)) || fail "$name"
  done
  info "$n color schemes removed"
fi

# ── Removing GTK Theme ──────────────────────────────
if [[ "$(cfg gtk)" == "true" ]]; then
  step "Removing GTK Theme"
  note "Removes MacTahoe Liquid KDE GTK themes"

  n=0
  for variant in MacTahoeLiquidKde-Light MacTahoeLiquidKde-Dark; do
    [[ -d "$HOME/.themes/$variant" ]] || continue
    rm -rf "$HOME/.themes/$variant" 2>/dev/null && ok "$variant removed" && n=$((n+1)) || fail "$variant"
  done

  # remove gtk-4.0 theme overrides (restore KDE default)
  rm -rf "$HOME/.config/gtk-4.0/assets" "$HOME/.config/gtk-4.0/windows-assets" 2>/dev/null
  rm -f "$HOME/.config/gtk-4.0/gtk.css" "$HOME/.config/gtk-4.0/gtk-dark.css" "$HOME/.config/gtk-4.0/gtk-Dark.css" "$HOME/.config/gtk-4.0/gtk-Light.css" 2>/dev/null

  # reset GTK theme via KDE + gsettings
  for _q in qdbus6 qdbus; do
    command -v "$_q" &>/dev/null && {
      "$_q" org.kde.GtkConfig /GtkConfig org.kde.GtkConfig.setGtkTheme "Breeze" &>/dev/null || true
      break
    }
  done
  if command -v gsettings &>/dev/null; then
    gsettings reset org.gnome.desktop.interface gtk-theme &>/dev/null || true
    gsettings reset org.gnome.desktop.interface color-scheme &>/dev/null || true
  fi
  info "$n GTK themes removed"
fi

# ── Removing Plasmoids ──────────────────────────────
if [[ "$(cfg plasmoids)" == "true" ]]; then
  step "Removing Plasmoids"
  note "Removes custom Plasma widgets"
  n=0
  for widget in "$PLASMOIDS_DIR"/org.kde.mac-tahoe-liquid-kde.* "$PLASMOIDS_DIR"/org.kde.mactahoe-liquid-kde.*; do
    [[ -d "$widget" ]] || continue
    name=$(basename "$widget")
    rm -rf "$widget" 2>/dev/null && ok "$name" && n=$((n+1)) || fail "$name"
  done
  info "$n plasmoids removed"
fi

# ── Removing Liquid Glass ───────────────────────────
if [[ "$(cfg liquid_glass)" == "true" ]]; then
  step "Removing Liquid Glass"
  note "Unloads and removes the Liquid Glass KWin effect"

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

# ── Reset to Breeze defaults ─────────────────────────────────
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
