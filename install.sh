#!/usr/bin/env bash
# MacTahoe Liquid KDE — Installer
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO/src"
STEPS="$REPO/src/steps"
CONFIG="$REPO/features.json"
WALLPAPERS="$HOME/.local/share/wallpapers"
FONTS_DIR="$HOME/.local/share/fonts"
ICONS_DIR="$HOME/.local/share/icons"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; RESET='\033[0m'; BOLD='\033[1m'

ERRORS=()
STEP=0

ok()        { echo -e "  ${GREEN}✓${RESET}  $*"; }
reinstall() { echo -e "  ${YELLOW}↺${RESET}  $* (reinstalled)"; }
info()      { echo -e "  ${BOLD}$*${RESET}"; }
note()      { echo -e "  $*"; echo ""; }
warn()      { echo -e "  ${YELLOW}⚠${RESET}  $*"; }
fail()      { echo -e "  ${RED}✗${RESET}  $*"; ERRORS+=("$*"); }
step() {
  ((STEP++))
  echo ""
  echo -e "${GREEN}${BOLD}  ── Step ${STEP}: $* ─────────────────────────────${RESET}"
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
command -v kwriteconfig6 &>/dev/null && ok "kwriteconfig6" || warn "kwriteconfig6 not found — fonts won't apply automatically"
command -v fc-cache      &>/dev/null && ok "fontconfig"    || warn "fc-cache not found"
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

# ── (future) Installing Icons ────────────────────────────────
# if [[ "$(cfg icons)" == "true" ]]; then
#   step "Installing Icons"
#   note "Downloads and installs the MacTahoe Liquid KDE icon theme"
#   run_step "step-icons.sh"
# fi
# ── (future) Installing Sounds ───────────────────────────────
# ── (future) Installing GTK Theme ────────────────────────────
# ── (future) Installing SDDM Theme ───────────────────────────
# ── (future) Installing Custom Apps ──────────────────────────

# ── Step 5: Applying Changes ─────────────────────────────────
step "Applying Changes"
note "Applies settings and tells KDE to reload"

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
    cursor_theme=""
    for theme in "$ICONS_DIR"/MacTahoeLiquidKde "$ICONS_DIR"/MacTahoeLiquidKde-Dark "$ICONS_DIR"/MacTahoeLiquidKde-Apple "$ICONS_DIR"/MacTahoeLiquidKde-Apple-White; do
      [[ -d "$theme/cursors" ]] && { cursor_theme=$(basename "$theme"); break; }
    done
    if [[ -n "$cursor_theme" ]]; then
      kwriteconfig6 --file kcminputrc --group Mouse --key cursorTheme "$cursor_theme"
      ok "cursor theme set ($cursor_theme)"
    else
      warn "cursor theme not found — set manually in System Settings"
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
echo -e "${GREEN}${BOLD}  ── Done ────────────────────────────────────────${RESET}"
if [[ ${#ERRORS[@]} -eq 0 ]]; then
  ok "MacTahoe Liquid KDE installed successfully"
else
  warn "${#ERRORS[@]} issue(s) — everything else installed fine:"
  for e in "${ERRORS[@]}"; do fail "$e"; done
fi
echo ""
echo -e "  ${BOLD}Log out and back in to apply all changes${RESET}"
echo ""