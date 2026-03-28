#!/usr/bin/env bash
# MacTahoe Liquid KDE — Installer
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO/src"
STEPS="$REPO/src/steps"
OFFLINE="$REPO/src/offline"
CONFIG="$REPO/features.json"
WALLPAPERS="$HOME/.local/share/wallpapers"
FONTS_DIR="$HOME/.local/share/fonts"
ICONS_DIR="$HOME/.local/share/icons"
PLASMOIDS_DIR="$HOME/.local/share/plasma/plasmoids"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; RESET='\033[0m'; BOLD='\033[1m'

ERRORS=()
STEP=0

ok()        { echo -e "  ${GREEN}✓${RESET}  $*"; }
reinstall() { echo -e "  ${YELLOW}↺${RESET}  $* (reinstalled)"; }
info()      { echo ""; echo -e "  ${BOLD}$*${RESET}"; }
note()      { echo -e "  $*"; echo ""; }
warn()      { echo -e "  ${YELLOW}⚠${RESET}  $*"; }
fail()      { echo -e "  ${RED}✗${RESET}  $*"; ERRORS+=("$*"); }
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

run_step() {
  local script="$1"
  if [[ ! -f "$STEPS/$script" ]]; then
    fail "$script not found (source missing)"
    return 1
  fi
  bash "$STEPS/$script" || true
}

[[ -d "$SRC" ]] || { echo -e "${RED}  Run from repo root.${RESET}" >&2; exit 1; }

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
  echo "     Please update KDE Plasma before installing."
  echo ""
  exit 1
fi

ok "KDE Plasma $plasma_ver"

# ── auto-install missing deps ─────────────────────────────────
_pkg_install() {
  if   command -v pacman &>/dev/null; then sudo pacman -S --noconfirm "$@"
  elif command -v yay    &>/dev/null; then yay   -S --noconfirm "$@"
  elif command -v paru   &>/dev/null; then paru  -S --noconfirm "$@"
  else fail "no package manager found — install $* manually"; return 1; fi
}

for _dep in curl unzip; do
  if command -v "$_dep" &>/dev/null; then
    ok "$_dep"
  else
    warn "$_dep not found — installing..."
    _pkg_install "$_dep" && ok "$_dep (installed)" || fail "$_dep (install failed)"
  fi
done
if command -v fc-cache &>/dev/null; then
  ok "fontconfig"
else
  warn "fontconfig not found — installing..."
  _pkg_install fontconfig && ok "fontconfig (installed)" || fail "fontconfig (install failed)"
fi
unset -f _pkg_install

command -v kwriteconfig6 &>/dev/null && ok "kwriteconfig6" || warn "kwriteconfig6 not found — fonts won't apply automatically"
[[ -f "$CONFIG" ]] && ok "features.json loaded"

# ── Step 2: Installing Wallpapers ─────────────────────────────
if [[ "$(cfg wallpapers)" == "true" ]]; then
  step "Installing Wallpapers"
  note "Downloads and installs MacTahoe Liquid KDE wallpaper packages"

  # snapshot before any downloads so installed/reinstalled reflects pre-run state
  declare -A _wp_pre=()
  for _d in "$WALLPAPERS"/*/; do [[ -d "$_d" ]] && _wp_pre["$(basename "$_d")"]=1; done

  run_step "step-wallpapers.sh"

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
    bak="$WALLPAPERS/.bak_${name}_$$"

    rm -rf "$tmp" 2>/dev/null || true
    if err=$(cp -r "$wp/." "$tmp/" 2>&1 || { mkdir -p "$tmp" && cp -r "$wp/." "$tmp/"; }); then
      # move dest aside first so mv never sees an existing dest dir
      rm -rf "$bak" 2>/dev/null || true
      [[ -d "$dest" ]] && { mv "$dest" "$bak" 2>/dev/null || rm -rf "$dest" 2>/dev/null || true; }
      if err2=$(mv "$tmp" "$dest" 2>&1); then
        rm -rf "$bak" 2>/dev/null || true
        if [[ -n "${_wp_pre[$name]+_}" ]]; then
          reinstall "$name"; n_re=$((n_re+1))
        else
          ok "$name (installed)"; n_inst=$((n_inst+1))
        fi
      else
        [[ -d "$bak" ]] && mv "$bak" "$dest" 2>/dev/null || true
        rm -rf "$tmp" 2>/dev/null || true
        fail "$name (move failed: ${err2:-unknown error})"
      fi
    else
      rm -rf "$tmp" 2>/dev/null || true
      fail "$name (copy failed: ${err:-unknown error})"
    fi
  done
  info "$((n_inst+n_re)) wallpapers — $n_inst installed, $n_re reinstalled"
fi

# ── Step 3: Installing Fonts ──────────────────────────────────
if [[ "$(cfg fonts)" == "true" ]]; then
  step "Installing Fonts"
  note "Downloads and installs SF Pro and SF Mono"

  run_step "step-fonts.sh"

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
        reinstall "$name"; g_re[$grp]=$(( ${g_re[$grp]:-0} + 1 ))
      else
        fail "$name (copy failed: ${err:-unknown error})"
      fi
    else
      if err=$(cp "$f" "$FONTS_DIR/" 2>&1); then
        ok "$name (installed)"; g_inst[$grp]=$(( ${g_inst[$grp]:-0} + 1 ))
      else
        fail "$name (copy failed: ${err:-unknown error})"
      fi
    fi
  done

  for grp in "SF Pro" "SF Mono" "Other"; do
    i=${g_inst[$grp]:-0}; r=${g_re[$grp]:-0}
    [[ $((i+r)) -eq 0 ]] && continue
    info "$grp — $i installed, $r reinstalled"
  done
  fc-cache -f "$FONTS_DIR" 2>/dev/null || true
fi

# ── (future) Installing Plasma Theme ─────────────────────────
# if [[ "$(cfg plasma_theme)" == "true" ]]; then
#   step "Installing Plasma Theme"
#   note "Installs the MacTahoe Liquid KDE Plasma desktop theme"
#   run_step "step-plasma.sh"
# fi
# ── (future) Installing Window Decorations ───────────────────
# ── (future) Installing Kvantum Theme ────────────────────────
# ── (future) Installing Color Schemes ────────────────────────

# ── Step 4: Installing Cursors ───────────────────────────────
if [[ "$(cfg cursors)" == "true" ]]; then
  step "Installing Cursors"
  note "Downloads and installs MacTahoe Liquid KDE cursor themes"

  # snapshot before any downloads so installed/reinstalled reflects pre-run state
  declare -A _cur_pre=()
  for _d in "$ICONS_DIR"/*/; do [[ -d "$_d" ]] && _cur_pre["$(basename "$_d")"]=1; done

  run_step "step-cursors.sh"

  mkdir -p "$ICONS_DIR"
  n_inst=0; n_re=0
  for theme in "$STEPS/cursors"/*/; do
    [[ -d "$theme" ]] || continue
    name=$(basename "$theme")
    [[ -d "$theme/cursors" ]] || { fail "$name (no cursors/ dir — skipping)"; continue; }

    dest="$ICONS_DIR/$name"
    tmp="$ICONS_DIR/.tmp_${name}_$$"
    bak="$ICONS_DIR/.bak_${name}_$$"

    rm -rf "$tmp" 2>/dev/null || true
    if err=$(cp -r "$theme/." "$tmp/" 2>&1 || { mkdir -p "$tmp" && cp -r "$theme/." "$tmp/"; }); then
      # move dest aside first so mv never sees an existing dest dir
      rm -rf "$bak" 2>/dev/null || true
      [[ -d "$dest" ]] && { mv "$dest" "$bak" 2>/dev/null || rm -rf "$dest" 2>/dev/null || true; }
      if err2=$(mv "$tmp" "$dest" 2>&1); then
        rm -rf "$bak" 2>/dev/null || true
        if [[ -n "${_cur_pre[$name]+_}" ]]; then
          reinstall "$name"; n_re=$((n_re+1))
        else
          ok "$name (installed)"; n_inst=$((n_inst+1))
        fi
      else
        [[ -d "$bak" ]] && mv "$bak" "$dest" 2>/dev/null || true
        rm -rf "$tmp" 2>/dev/null || true
        fail "$name (move failed: ${err2:-unknown error})"
      fi
    else
      rm -rf "$tmp" 2>/dev/null || true
      fail "$name (copy failed: ${err:-unknown error})"
    fi
  done
  info "$((n_inst+n_re)) cursor themes — $n_inst installed, $n_re reinstalled"
fi

# ── Step 5: Installing Icons ─────────────────────────────────
if [[ "$(cfg icons)" == "true" ]]; then
  step "Installing Icons"
  note "Downloads and installs MacTahoe Liquid KDE icon themes"

  # snapshot before any downloads so installed/reinstalled reflects pre-run state
  declare -A _ico_pre=()
  for _d in "$ICONS_DIR"/*/; do [[ -d "$_d" ]] && _ico_pre["$(basename "$_d")"]=1; done

  run_step "step-icons.sh"

  mkdir -p "$ICONS_DIR"
  n_inst=0; n_re=0
  for theme in "$STEPS/icons"/*/; do
    [[ -d "$theme" ]] || continue
    name=$(basename "$theme")
    [[ -f "$theme/index.theme" ]] || { fail "$name (no index.theme — skipping)"; continue; }

    dest="$ICONS_DIR/$name"
    tmp="$ICONS_DIR/.tmp_${name}_$$"
    bak="$ICONS_DIR/.bak_${name}_$$"

    rm -rf "$tmp" 2>/dev/null || true
    if err=$(cp -r "$theme/." "$tmp/" 2>&1 || { mkdir -p "$tmp" && cp -r "$theme/." "$tmp/"; }); then
      rm -rf "$bak" 2>/dev/null || true
      [[ -d "$dest" ]] && { mv "$dest" "$bak" 2>/dev/null || rm -rf "$dest" 2>/dev/null || true; }
      if err2=$(mv "$tmp" "$dest" 2>&1); then
        rm -rf "$bak" 2>/dev/null || true
        if [[ -n "${_ico_pre[$name]+_}" ]]; then
          reinstall "$name"; n_re=$((n_re+1))
        else
          ok "$name (installed)"; n_inst=$((n_inst+1))
        fi
      else
        [[ -d "$bak" ]] && mv "$bak" "$dest" 2>/dev/null || true
        rm -rf "$tmp" 2>/dev/null || true
        fail "$name (move failed: ${err2:-unknown error})"
      fi
    else
      rm -rf "$tmp" 2>/dev/null || true
      fail "$name (copy failed: ${err:-unknown error})"
    fi
  done
  _n=$(( n_inst + n_re ))
  [[ $_n -eq 1 ]] && _lbl="icon theme" || _lbl="icon themes"
  info "$_n $_lbl — $n_inst installed, $n_re reinstalled"
  unset _n _lbl
fi
# ── Step: Installing Plasmoids ───────────────────────────────
if [[ "$(cfg plasmoids)" == "true" ]]; then
  step "Installing Plasmoids"
  note "Installs custom Plasma widgets from src/offline/plasmoids"

  mkdir -p "$PLASMOIDS_DIR"
  n_inst=0; n_re=0
  for widget in "$OFFLINE/plasmoids"/*/; do
    [[ -d "$widget" ]] || continue
    name=$(basename "$widget")
    [[ -f "$widget/metadata.json" ]] || { fail "$name (no metadata.json — skipping)"; continue; }

    dest="$PLASMOIDS_DIR/$name"
    tmp="$PLASMOIDS_DIR/.tmp_${name}_$$"
    bak="$PLASMOIDS_DIR/.bak_${name}_$$"

    rm -rf "$tmp" 2>/dev/null || true
    if err=$(cp -r "$widget/." "$tmp/" 2>&1 || { mkdir -p "$tmp" && cp -r "$widget/." "$tmp/"; }); then
      rm -rf "$bak" 2>/dev/null || true
      was_present=false
      [[ -d "$dest" ]] && { was_present=true; mv "$dest" "$bak" 2>/dev/null || rm -rf "$dest" 2>/dev/null || true; }
      if err2=$(mv "$tmp" "$dest" 2>&1); then
        rm -rf "$bak" 2>/dev/null || true
        if $was_present; then
          reinstall "$name"; n_re=$((n_re+1))
        else
          ok "$name (installed)"; n_inst=$((n_inst+1))
        fi
      else
        [[ -d "$bak" ]] && mv "$bak" "$dest" 2>/dev/null || true
        rm -rf "$tmp" 2>/dev/null || true
        fail "$name (move failed: ${err2:-unknown error})"
      fi
    else
      rm -rf "$tmp" 2>/dev/null || true
      fail "$name (copy failed: ${err:-unknown error})"
    fi
  done
  _n=$(( n_inst + n_re ))
  [[ $_n -eq 1 ]] && _lbl="plasmoid" || _lbl="plasmoids"
  info "$_n $_lbl — $n_inst installed, $n_re reinstalled"
  unset _n _lbl
fi

# ── (future) Installing Sounds ───────────────────────────────
# ── (future) Installing GTK Theme ────────────────────────────
# ── (future) Installing SDDM Theme ───────────────────────────
# ── (future) Installing Custom Apps ──────────────────────────

# ── Step 5: Applying Changes ─────────────────────────────────
step "Applying Changes"
note "Applies settings and tells KDE to reload"

# ── phase 1: write config files (before layout, so new panels read them) ──
icon_theme=""
cursor_theme=""

if command -v kwriteconfig6 &>/dev/null; then
  if [[ "$(cfg fonts)" == "true" ]]; then
    kwriteconfig6 --file kdeglobals --group General --key font                 "SF Pro Text,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key menuFont             "SF Pro Text,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key toolBarFont          "SF Pro Text,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key taskbarFont          "SF Pro Text,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key smallestReadableFont "SF Pro Text,8,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key fixed                "SF Mono,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group WM      --key activeFont           "SF Pro Display,11,-1,5,63,0,0,0,0,0"
    ok "KDE fonts configured"
  fi

  if [[ "$(cfg cursors)" == "true" ]]; then
    for theme in "$ICONS_DIR"/MacTahoeLiquidKde "$ICONS_DIR"/MacTahoeLiquidKde-Dark "$ICONS_DIR"/MacTahoeLiquidKde-Apple "$ICONS_DIR"/MacTahoeLiquidKde-Apple-White; do
      [[ -d "$theme/cursors" ]] && { cursor_theme=$(basename "$theme"); break; }
    done
    if [[ -n "$cursor_theme" ]]; then
      kwriteconfig6 --file kcminputrc --group Mouse --key cursorTheme "$cursor_theme"
      ok "Cursor config written"
    else
      warn "cursor theme not found — set manually in System Settings"
    fi
  fi

  if [[ "$(cfg icons)" == "true" ]]; then
    for theme in "$ICONS_DIR"/MacTahoeLiquidKde-Icons "$ICONS_DIR"/MacTahoeLiquidKde-Icons-dark; do
      [[ -f "$theme/index.theme" ]] && { icon_theme=$(basename "$theme"); break; }
    done
    if [[ -n "$icon_theme" ]]; then
      kwriteconfig6 --file kdeglobals --group Icons --key Theme "$icon_theme"
      ok "Icon config written"
    else
      warn "icon theme not found — set manually in System Settings"
    fi
  fi
fi

# ── phase 2: layout (new panels read the config we just wrote) ──
if [[ "$(cfg layout)" == "true" ]]; then
  _layout="$REPO/src/offline/layouts/mactahoe.js"
  if [[ -f "$_layout" ]]; then
    _qdbus=""
    for _q in qdbus6 qdbus; do command -v "$_q" &>/dev/null && { _qdbus="$_q"; break; }; done
    if [[ -n "$_qdbus" ]]; then
      "$_qdbus" org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$(cat "$_layout")" &>/dev/null \
        && ok "Layout applied (top bar + bottom dock)" \
        || warn "layout script failed — set layout manually"
      sleep 2  # let Plasma finish creating panels
    else
      warn "qdbus not found — layout not applied"
    fi
  fi
fi

# ── phase 3: live-apply themes (panels now exist with correct config) ──
if [[ -n "$icon_theme" ]] && command -v plasma-apply-icontheme &>/dev/null; then
  plasma-apply-icontheme "$icon_theme" &>/dev/null || true
  ok "Icon theme applied"
fi

if [[ -n "$cursor_theme" ]] && command -v plasma-apply-cursortheme &>/dev/null; then
  plasma-apply-cursortheme "$cursor_theme" &>/dev/null || true
  ok "Cursor theme applied"
fi

if [[ "$(cfg wallpapers)" == "true" ]]; then
  wp_path="$WALLPAPERS/MacTahoe"
  if [[ -d "$wp_path" ]] && command -v plasma-apply-wallpaperimage &>/dev/null; then
    plasma-apply-wallpaperimage "$wp_path" &>/dev/null || true
    ok "Wallpaper set to MacTahoe (light/dark)"
  fi
fi

# ── phase 4: rebuild caches and signal reload ──
if command -v kbuildsycoca6 &>/dev/null; then
  kbuildsycoca6 --noincremental 2>/dev/null \
    && ok "KDE system cache rebuilt" || warn "kbuildsycoca6 failed (non-fatal)"
fi

for qdbus_cmd in qdbus6 qdbus; do
  command -v "$qdbus_cmd" &>/dev/null && {
    "$qdbus_cmd" org.kde.KWin /KWin org.kde.KWin.reconfigure &>/dev/null \
      && ok "KWin reconfigured" || warn "KWin reconfigure failed (non-fatal)"
    break
  }
done

# flush icon caches so widgets (trash, etc.) pick up new theme immediately
rm -rf "$HOME/.cache/icon-cache.kcache" 2>/dev/null || true
rm -rf "$HOME/.cache/plasma-svgelements-"* 2>/dev/null || true
rm -rf "$HOME/.cache/plasma_theme_"* 2>/dev/null || true
find "$HOME/.cache" -maxdepth 1 -name "ksycoca6*" -delete 2>/dev/null || true
ok "Icon and widget caches flushed"

if command -v dbus-send &>/dev/null; then
  dbus-send --session --type=signal /KIconLoader org.kde.KIconLoader.iconChanged 2>/dev/null || true
  dbus-send --session --type=signal /KGlobalSettings org.kde.KGlobalSettings.notifyChange int32:4 int32:0 2>/dev/null || true
  dbus-send --session --dest=org.kde.plasmashell \
    /PlasmaShell org.kde.PlasmaShell.refreshCurrentShell 2>/dev/null \
    && ok "Plasma shell refreshed" || warn "Plasma shell refresh failed (non-fatal)"
fi

# ── Done ──────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  ── Done${RESET}"
if [[ ${#ERRORS[@]} -eq 0 ]]; then
  ok "MacTahoe Liquid KDE installed successfully"
else
  warn "${#ERRORS[@]} issue(s) — everything else installed fine:"
  for e in "${ERRORS[@]}"; do fail "$e"; done
fi
echo ""