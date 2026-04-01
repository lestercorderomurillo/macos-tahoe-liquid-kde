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

# ── feature flags ────────────────────────────────────────
# All features with their defaults
_ALL_FEATURES=(wallpapers fonts cursors plasma_theme window_decorations kvantum color_schemes icons plasmoids acrylic_glass layout sounds gtk sddm apps no_download)

# declare associative arrays for feature state and CLI overrides
declare -A _feat=()
declare -A _cli=()
_theme_mode=""
_do_save=false
_do_reset=false

# 1. load defaults from features.json
_cfg_read() {
  local key="$1"
  [[ -f "$CONFIG" ]] || { echo "true"; return; }
  local val
  val=$(sed -n 's/.*"'"$key"'"[[:space:]]*:[[:space:]]*\("[^"]*"\|true\|false\).*/\1/p' "$CONFIG" | tr -d '"' | head -1)
  echo "${val:-true}"
}

for _f in "${_ALL_FEATURES[@]}"; do
  _feat[$_f]="$(_cfg_read "$_f")"
done
_theme_mode="$(_cfg_read "theme_mode")"
[[ "$_theme_mode" =~ ^(auto|light|dark)$ ]] || _theme_mode="auto"

# 2. parse CLI flags (override features.json)
for _arg in "$@"; do
  case "$_arg" in
    --light)       _theme_mode="light" ;;
    --dark)        _theme_mode="dark" ;;
    --auto)        _theme_mode="auto" ;;
    --save)        _do_save=true ;;
    --reset)       _do_reset=true ;;
    --no-download|--offline) _cli[no_download]="true" ;;
    --download)    _cli[no_download]="false" ;;
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

# 3. --reset: restore features.json to all-true defaults
if $_do_reset; then
  cat > "$CONFIG" <<'DEFAULTS'
{
  "wallpapers":          true,
  "fonts":               true,
  "cursors":             true,
  "plasma_theme":        true,
  "window_decorations":  true,
  "kvantum":             true,
  "color_schemes":       true,
  "icons":               true,
  "plasmoids":           true,
  "acrylic_glass":        true,
  "layout":              true,
  "sounds":              true,
  "gtk":                 true,
  "sddm":               true,
  "apps":                true,
  "no_download":         true,
  "theme_mode":          "auto"
}
DEFAULTS
  echo -e "  ${GREEN}✓${RESET}  features.json reset to defaults"
  # reload after reset
  for _f in "${_ALL_FEATURES[@]}"; do _feat[$_f]="$(_cfg_read "$_f")"; done
  _theme_mode="auto"
fi

# 4. apply CLI overrides on top
for _f in "${_ALL_FEATURES[@]}"; do
  [[ -n "${_cli[$_f]:-}" ]] && _feat[$_f]="${_cli[$_f]}"
done

# 5. --save: persist current state back to features.json
if $_do_save; then
  {
    echo "{"
    for _f in "${_ALL_FEATURES[@]}"; do
      printf '  "%-20s %s\n' "${_f}\":" "${_feat[$_f]},"
    done
    printf '  "%-20s "%s"\n' 'theme_mode":' "$_theme_mode"
    echo "}"
  } > "$CONFIG"
  echo -e "  ${GREEN}✓${RESET}  features.json saved"
fi

# convenience: cfg reads the resolved value (file + CLI merged)
cfg() { echo "${_feat[$1]:-true}"; }

NO_DOWNLOAD="${_feat[no_download]}"

run_step() {
  local script="$1"
  if [[ ! -f "$STEPS/$script" ]]; then
    fail "$script not found (source missing)"
    return 1
  fi
  bash "$STEPS/$script" || true
}

[[ -d "$SRC" ]] || { echo -e "${RED}  Run from repo root.${RESET}" >&2; exit 1; }

# ── BETA WARNING ─────────────────────────────────────────────
echo ""
echo -e "  ${RED}${BOLD}In development — Install at your own risk.${RESET}"
echo ""
read -p "  Continue? [Y/n] " _confirm
[[ "$_confirm" =~ ^[Nn]$ ]] && { echo "  Aborted."; exit 0; }
echo ""

sudo -v || { echo -e "  ${RED}sudo required.${RESET}"; exit 1; }

# ── Verification ──────────────────────────────────────
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

_auto_dep() {
  local cmd="$1" pkg="${2:-$1}"
  if command -v "$cmd" &>/dev/null; then
    ok "$cmd"
  else
    warn "$cmd not found — installing..."
    _pkg_install "$pkg" && ok "$cmd (installed)" || fail "$cmd (install failed)"
  fi
}

_auto_dep curl
_auto_dep unzip
_auto_dep fc-cache fontconfig
_auto_dep kwriteconfig6 kconfig
_auto_dep cmake
_auto_dep g++ gcc
_auto_dep pkg-config pkgconf
_auto_dep dbus-monitor dbus

# panel colorizer (needed for transparent top bar)
if [[ "$(cfg layout)" == "true" ]]; then
  _colorizer_dir="$HOME/.local/share/plasma/plasmoids/luisbocanegra.panel.colorizer"
  if [[ -d "$_colorizer_dir" ]]; then
    ok "Panel Colorizer"
  else
    warn "Panel Colorizer not found — installing..."
    if command -v kpackagetool6 &>/dev/null; then
      kpackagetool6 -i "https://store.kde.org/p/2130967" -t Plasma/Applet &>/dev/null \
        || kpackagetool6 --install "luisbocanegra.panel.colorizer" -t Plasma/Applet &>/dev/null \
        || true
    fi
    # fallback: install via plasma-discover CLI or paru
    if [[ ! -d "$_colorizer_dir" ]]; then
      if command -v paru &>/dev/null; then
        paru -S --noconfirm plasma6-applets-panel-colorizer 2>/dev/null || true
      elif command -v yay &>/dev/null; then
        yay -S --noconfirm plasma6-applets-panel-colorizer 2>/dev/null || true
      fi
    fi
    [[ -d "$_colorizer_dir" ]] && ok "Panel Colorizer (installed)" || warn "Panel Colorizer not installed — top bar won't be transparent. Install manually from KDE Store."
  fi
fi

[[ -f "$CONFIG" ]] && ok "features.json loaded"

# ── Installing Wallpapers ─────────────────────────────
if [[ "$(cfg wallpapers)" == "true" ]]; then
  step "Installing Wallpapers"
  note "Downloads and installs MacTahoe Liquid KDE wallpaper packages"

  # snapshot before any downloads so installed/reinstalled reflects pre-run state
  declare -A _wp_pre=()
  for _d in "$WALLPAPERS"/*/; do [[ -d "$_d" ]] && _wp_pre["$(basename "$_d")"]=1; done

  if $NO_DOWNLOAD && compgen -G "$SRC/steps/wallpapers/MacTahoe/contents/images/*" &>/dev/null; then
    ok "Wallpapers already downloaded"
  else
    run_step "step-wallpapers.sh"
  fi

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

# ── Installing Fonts ──────────────────────────────────
if [[ "$(cfg fonts)" == "true" ]]; then
  step "Installing Fonts"
  note "Downloads and installs SF Pro and SF Mono"

  if $NO_DOWNLOAD && compgen -G "$SRC/steps/fonts/*.otf" &>/dev/null; then
    ok "Fonts already downloaded"
  else
    run_step "step-fonts.sh"
  fi

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

# ── Installing Plasma Theme ──────────────────────────────────
if [[ "$(cfg plasma_theme)" == "true" ]]; then
  step "Installing Plasma Theme"
  note "Installs MacTahoe Liquid KDE Plasma desktop theme (light and dark)"

  _pt_src="$OFFLINE/plasma-theme"
  _pt_dest="$HOME/.local/share/plasma/desktoptheme"
  _pt_n=0

  if [[ -d "$_pt_src" ]]; then
    mkdir -p "$_pt_dest"
    for variant in MacTahoeLiquidKde-Dark MacTahoeLiquidKde-Light; do
      [[ -d "$_pt_src/$variant" ]] || continue
      _existed=false
      [[ -d "$_pt_dest/$variant" ]] && _existed=true
      cp -rf "$_pt_src/$variant" "$_pt_dest/"
      if [[ -d "$_pt_dest/$variant" ]]; then
        if $_existed; then
          reinstall "$variant"
        else
          ok "$variant installed"
        fi
        _pt_n=$((_pt_n+1))
      else
        fail "$variant (copy failed)"
      fi
    done
    info "$_pt_n Plasma themes installed"
    # theme variant is applied later by theme-switch.sh (auto light/dark)
  else
    fail "Plasma theme source not found at $_pt_src"
  fi
fi
# ── Installing Window Decorations ────────────────────────────
if [[ "$(cfg window_decorations)" == "true" ]]; then
  step "Installing Window Decorations"
  note "Installs macOS-style Aurorae window decorations (title bar buttons)"

  _au_src="$OFFLINE/aurorae"
  _au_dest="$HOME/.local/share/aurorae/themes"
  _au_n=0

  if [[ -d "$_au_src" ]]; then
    mkdir -p "$_au_dest"
    for _mode in Dark Light; do
      name="MacTahoeLiquidKde-${_mode}"
      _dest_dir="$_au_dest/$name"
      _existed=false
      [[ -d "$_dest_dir" ]] && _existed=true
      mkdir -p "$_dest_dir"
      # decoration SVG
      cp -f "$_au_src/$name/decoration.svg" "$_dest_dir/" 2>/dev/null
      # rc config
      cp -f "$_au_src/${name}rc" "$_dest_dir/${name}rc" 2>/dev/null
      # button icons
      cp -f "$_au_src/icons-${_mode}"/*.svg "$_dest_dir/" 2>/dev/null
      # metadata (replace theme_name placeholder)
      sed "s/theme_name/${name}/g" "$_au_src/metadata.desktop" > "$_dest_dir/metadata.desktop"
      sed "s/theme_name/${name}/g" "$_au_src/metadata.json" > "$_dest_dir/metadata.json"
      if $_existed; then reinstall "$name"; else ok "$name installed"; fi
      _au_n=$((_au_n+1))
    done
    info "$_au_n Aurorae themes installed"

    # apply aurorae decoration to kwinrc
    _kwinrc="$HOME/.config/kwinrc"
    _theme_name="MacTahoeLiquidKde-Dark"
    if [[ "$_theme_mode" == "light" ]]; then
      _theme_name="MacTahoeLiquidKde-Light"
    fi
    kwriteconfig6 --file "$_kwinrc" --group "org.kde.kdecoration2" --key "library" "org.kde.kwin.aurorae" 2>/dev/null
    kwriteconfig6 --file "$_kwinrc" --group "org.kde.kdecoration2" --key "theme" "__aurorae__svg__${_theme_name}" 2>/dev/null
    kwriteconfig6 --file "$_kwinrc" --group "org.kde.kdecoration2" --key "ButtonsOnLeft" "XIA" 2>/dev/null
    kwriteconfig6 --file "$_kwinrc" --group "org.kde.kdecoration2" --key "ButtonsOnRight" "" 2>/dev/null
    for _q in qdbus6 qdbus; do
      command -v "$_q" &>/dev/null && { "$_q" org.kde.KWin /KWin reconfigure 2>/dev/null || true; break; }
    done
    ok "Window decoration set to ${_theme_name}"
  else
    fail "Aurorae source not found at $_au_src"
  fi
fi
# ── Installing Kvantum Theme ─────────────────────────────────
if [[ "$(cfg kvantum)" == "true" ]]; then
  step "Installing Kvantum Theme"
  note "Installs Kvantum engine and the MacTahoe Liquid KDE Kvantum theme"

  _auto_dep kvantummanager kvantum

  # copy theme to Kvantum config dir
  _kv_src="$OFFLINE/kvantum/mac-tahoe-liquid-kde"
  _kv_dest="$HOME/.config/Kvantum/mac-tahoe-liquid-kde"
  _kv_existed=false
  [[ -d "$_kv_dest" ]] && ls "$_kv_dest"/*.kvconfig &>/dev/null && _kv_existed=true
  if [[ -d "$_kv_src" ]]; then
    mkdir -p "$_kv_dest"
    cp -f "$_kv_src"/*.kvconfig "$_kv_dest/" 2>/dev/null
    cp -f "$_kv_src"/*.svg      "$_kv_dest/" 2>/dev/null

    if [[ -d "$_kv_dest" ]] && ls "$_kv_dest"/*.kvconfig &>/dev/null; then
      if $_kv_existed; then
        reinstall "mac-tahoe-liquid-kde theme"
      else
        ok "mac-tahoe-liquid-kde theme installed"
      fi
    else
      fail "mac-tahoe-liquid-kde theme (copy failed)"
    fi

    # set Qt widget style to kvantum so the theme actually takes effect
    if command -v kwriteconfig6 &>/dev/null; then
      kwriteconfig6 --file kdeglobals --group KDE --key widgetStyle kvantum
      ok "Widget style installed"
    fi
    # theme variant is applied later by theme-switch.sh (auto light/dark)
  else
    fail "Kvantum theme source not found at $_kv_src"
  fi
fi
# ── Installing Color Schemes ────────────────────────────────
if [[ "$(cfg color_schemes)" == "true" ]]; then
  step "Installing Color Schemes"
  note "Installs MacTahoe Liquid KDE color schemes (light and dark)"

  _cs_src="$OFFLINE/color-schemes"
  _cs_dest="$HOME/.local/share/color-schemes"
  _cs_n=0

  if [[ -d "$_cs_src" ]]; then
    mkdir -p "$_cs_dest"
    for cs in "$_cs_src"/*.colors; do
      [[ -f "$cs" ]] || continue
      name=$(basename "$cs" .colors)
      _existed=false
      [[ -f "$_cs_dest/$(basename "$cs")" ]] && _existed=true
      cp -f "$cs" "$_cs_dest/"
      if $_existed; then
        reinstall "$name"
      else
        ok "$name installed"
      fi
      _cs_n=$((_cs_n+1))
    done
    info "$_cs_n color schemes installed"
  else
    fail "Color scheme source not found at $_cs_src"
  fi
fi

# ── Installing GTK Theme ────────────────────────────────────
if [[ "$(cfg gtk)" == "true" ]]; then
  step "Installing GTK Theme"
  note "Installs MacTahoe Liquid KDE GTK theme (light and dark)"

  _gtk_src="$OFFLINE/gtk"
  _gtk_dest="$HOME/.themes"
  _gtk_n=0

  if [[ -d "$_gtk_src" ]]; then
    mkdir -p "$_gtk_dest"
    for variant in MacTahoeLiquidKde-Light MacTahoeLiquidKde-Dark; do
      [[ -d "$_gtk_src/$variant" ]] || continue
      _existed=false
      [[ -d "$_gtk_dest/$variant" ]] && _existed=true
      cp -rf "$_gtk_src/$variant" "$_gtk_dest/"
      if [[ -d "$_gtk_dest/$variant" ]]; then
        if $_existed; then
          reinstall "$variant"
        else
          ok "$variant installed"
        fi
        _gtk_n=$((_gtk_n+1))
      else
        fail "$variant (copy failed)"
      fi
    done
    # NEVER write to ~/.config/gtk-4.0/ — KDE's plasma-integration manages it
    info "$_gtk_n GTK themes installed"
    # theme variant is applied later by theme-switch.sh (auto light/dark)
  else
    fail "GTK theme source not found at $_gtk_src"
  fi
fi

# ── Installing Cursors ──────────────────────────────────────
if [[ "$(cfg cursors)" == "true" ]]; then
  step "Installing Cursors"
  note "Downloads and installs MacTahoe Liquid KDE cursor themes"

  # snapshot before any downloads so installed/reinstalled reflects pre-run state
  declare -A _cur_pre=()
  for _d in "$ICONS_DIR"/*/; do [[ -d "$_d" ]] && _cur_pre["$(basename "$_d")"]=1; done

  if $NO_DOWNLOAD && [[ -d "$SRC/steps/cursors/MacTahoeLiquidKde/cursors" ]]; then
    ok "Cursors already downloaded"
  else
    run_step "step-cursors.sh"
  fi

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

# ── Installing Icons ─────────────────────────────────
if [[ "$(cfg icons)" == "true" ]]; then
  step "Installing Icons"
  note "Downloads and installs MacTahoe Liquid KDE icon themes"

  # snapshot before any downloads so installed/reinstalled reflects pre-run state
  declare -A _ico_pre=()
  for _d in "$ICONS_DIR"/*/; do [[ -d "$_d" ]] && _ico_pre["$(basename "$_d")"]=1; done

  if $NO_DOWNLOAD && [[ -d "$SRC/steps/icons/MacTahoeLiquidKde-Icons" ]]; then
    ok "Icons already downloaded"
  else
    run_step "step-icons.sh"
  fi

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
  # ensure dark theme inherits from light so missing icons fall back correctly
  _dark_idx="$ICONS_DIR/MacTahoeLiquidKde-Icons-dark/index.theme"
  if [[ -f "$_dark_idx" ]] && ! grep -q "Inherits=MacTahoeLiquidKde-Icons," "$_dark_idx"; then
    sed -i 's/^Inherits=.*/Inherits=MacTahoeLiquidKde-Icons,hicolor,breeze/' "$_dark_idx"
  fi

  # rebuild per-theme icon caches so GTK/Qt apps pick up new icons immediately
  for theme in "$ICONS_DIR"/MacTahoeLiquidKde-Icons*/; do
    [[ -d "$theme" ]] || continue
    if command -v gtk-update-icon-cache &>/dev/null; then
      gtk-update-icon-cache -f -t "$theme" 2>/dev/null || true
    fi
  done

  _n=$(( n_inst + n_re ))
  [[ $_n -eq 1 ]] && _lbl="icon theme" || _lbl="icon themes"
  info "$_n $_lbl — $n_inst installed, $n_re reinstalled"
  unset _n _lbl
fi
# ── Installing Plasmoids ───────────────────────────────
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

# ── Installing Global Menu Plasma Applet ────────────────
if [[ "$(cfg plasmoids)" == "true" ]]; then
  step "Installing Global Menu"
  note "Builds and installs the Global Menu C++ Plasma applet from source"

  _gm_src="$OFFLINE/plasma-applets/globalmenu"
  _gm_build="$_gm_src/build"
  if [[ -f "$_gm_src/CMakeLists.txt" ]]; then
    _missing=false
    for _dep in cmake g++ pkg-config; do
      command -v "$_dep" &>/dev/null || { warn "$_dep not found — needed to build Global Menu"; _missing=true; }
    done
    pkg-config --exists dbusmenu-lxqt 2>/dev/null || {
      warn "libdbusmenu-lxqt not found — installing"
      sudo pacman -S --noconfirm libdbusmenu-lxqt 2>/dev/null \
        || paru -S --noconfirm libdbusmenu-lxqt 2>/dev/null \
        || yay -S --noconfirm libdbusmenu-lxqt 2>/dev/null \
        || { warn "could not install libdbusmenu-lxqt — skipping Global Menu build"; _missing=true; }
    }

    if ! $_missing; then
      rm -rf "$_gm_build"
      mkdir -p "$_gm_build"

      if cmake -S "$_gm_src" -B "$_gm_build" -DCMAKE_BUILD_TYPE=Release &>/dev/null; then
        if make -C "$_gm_build" -j"$(nproc)" &>/dev/null; then
          ok "Global Menu built"
          _gm_so="$_gm_build/bin/plasma/applets/org.kde.mac.tahoe.globalmenu.so"
          # prefer user-local path (no sudo); fall back to system path
          _gm_dest_user="$HOME/.local/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.globalmenu.so"
          _gm_dest_sys="/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.globalmenu.so"

          if [[ -f "$_gm_so" ]]; then
            mkdir -p "$(dirname "$_gm_dest_user")"
            if cp "$_gm_so" "$_gm_dest_user"; then
              ok "Global Menu installed (user-local)"
            elif sudo cp "$_gm_so" "${_gm_dest_sys}.tmp" && sudo mv -f "${_gm_dest_sys}.tmp" "$_gm_dest_sys"; then
              ok "Global Menu installed (system)"
            else
              fail "Global Menu: could not install .so"
            fi
          else
            fail "Global Menu: .so not found after build — check cmake output"
          fi
        else
          fail "Global Menu: build failed"
        fi
      else
        fail "Global Menu: cmake configure failed"
      fi
    fi
  else
    warn "Global Menu source not found — skipping"
  fi
fi

# ── Installing Acrylic Glass KWin Effect ────────────────
if [[ "$(cfg acrylic_glass)" == "true" ]]; then
  step "Installing Acrylic Glass"
  note "Builds and installs the Acrylic Glass KWin effect from source"

  _lg_src="$OFFLINE/kwin-effects/acrylic-glass"
  _lg_build="$_lg_src/build"
  if [[ -f "$_lg_src/CMakeLists.txt" ]]; then
    # check build deps
    _missing=false
    for _dep in cmake g++ pkg-config; do
      command -v "$_dep" &>/dev/null || { warn "$_dep not found — needed to build Acrylic Glass"; _missing=true; }
    done

    if ! $_missing; then
      # clean stale generated shaders and build dir
      rm -rf "$_lg_build"
      rm -f "$_lg_src/src/shaders/onscreen_rounded_core.frag" "$_lg_src/src/shaders/onscreen_rounded.frag"
      mkdir -p "$_lg_build"

      # disable original glass effect if enabled (conflicts)
      kwriteconfig6 --file kwinrc --group Plugins --key glassEnabled false 2>/dev/null || true
      kwriteconfig6 --file kwinrc --group Plugins --key blurEnabled false 2>/dev/null || true
      _qdbus_pre=""
      for _q in qdbus6 qdbus; do command -v "$_q" &>/dev/null && { _qdbus_pre="$_q"; break; }; done
      if [[ -n "$_qdbus_pre" ]]; then
        "$_qdbus_pre" org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect glass &>/dev/null || true
        "$_qdbus_pre" org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect blur &>/dev/null || true
      fi

      if cmake -S "$_lg_src" -B "$_lg_build" -DCMAKE_BUILD_TYPE=Release &>/dev/null; then
        if make -C "$_lg_build" -j"$(nproc)" &>/dev/null; then
          ok "Acrylic Glass built"
          # install .so files (requires write access to plugin dir)
          _plugin_dir=$(qmake6 -query QT_INSTALL_PLUGINS 2>/dev/null \
            || qtpaths6 --plugin-dir 2>/dev/null \
            || pkg-config --variable=plugindir Qt6Core 2>/dev/null \
            || echo "/usr/lib/qt6/plugins")
          _effect_so="$_lg_build/src/liquidglass.so"
          _config_so="$_lg_build/src/kcm/kwin_liquidglass_config.so"
          _dest_effect="$_plugin_dir/kwin/effects/plugins/liquidglass.so"
          _dest_config="$_plugin_dir/kwin/effects/configs/kwin_liquidglass_config.so"

          if [[ -f "$_effect_so" ]]; then
            # fully disable and unload the effect before replacing .so to avoid crash
            _qdbus_lg=""
            for _q in qdbus6 qdbus; do command -v "$_q" &>/dev/null && { _qdbus_lg="$_q"; break; }; done

            # step 1: disable in config
            kwriteconfig6 --file kwinrc --group Plugins --key liquidglassEnabled false 2>/dev/null || true

            # step 2: unload from KWin and reconfigure so it fully releases the .so
            if [[ -n "$_qdbus_lg" ]]; then
              "$_qdbus_lg" org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect liquidglass &>/dev/null || true
              "$_qdbus_lg" org.kde.KWin /KWin org.kde.KWin.reconfigure &>/dev/null || true
              sleep 2
            fi
            ok "Acrylic Glass unloaded for safe upgrade"

            if sudo cp "$_effect_so" "${_dest_effect}.tmp" && sudo mv -f "${_dest_effect}.tmp" "$_dest_effect" && \
               sudo cp "$_config_so" "${_dest_config}.tmp" && sudo mv -f "${_dest_config}.tmp" "$_dest_config" 2>/dev/null; then
              ok "Acrylic Glass installed"
              # write clean preset — must match blur.kcfg defaults exactly
              _lg_grp="Effect-liquidglass"
              kwriteconfig6 --file kwinrc --group "$_lg_grp" --key BlurStrength       2.0  2>/dev/null || true
              kwriteconfig6 --file kwinrc --group "$_lg_grp" --key NoiseStrength       2    2>/dev/null || true
              kwriteconfig6 --file kwinrc --group "$_lg_grp" --key RgbDriftStrength    84.0 2>/dev/null || true
              kwriteconfig6 --file kwinrc --group "$_lg_grp" --key MagnifyGlassStrength 0.025 2>/dev/null || true
              kwriteconfig6 --file kwinrc --group "$_lg_grp" --key RefractionWidth     56.0 2>/dev/null || true
              kwriteconfig6 --file kwinrc --group "$_lg_grp" --key HighlightWidth      12.0 2>/dev/null || true
              kwriteconfig6 --file kwinrc --group "$_lg_grp" --key HighlightStrength   0.40 2>/dev/null || true
              kwriteconfig6 --file kwinrc --group "$_lg_grp" --key ShadowStrength      2.50 2>/dev/null || true
              kwriteconfig6 --file kwinrc --group "$_lg_grp" --key TopCornerRadius     22   2>/dev/null || true
              kwriteconfig6 --file kwinrc --group "$_lg_grp" --key BottomCornerRadius  22   2>/dev/null || true
              kwriteconfig6 --file kwinrc --group "$_lg_grp" --key MenuCornerRadius    0    2>/dev/null || true
              kwriteconfig6 --file kwinrc --group "$_lg_grp" --key DockCornerRadius    22   2>/dev/null || true
              ok "Acrylic Glass preset installed"
              # enable in config — will load on next KWin start
              kwriteconfig6 --file kwinrc --group Plugins --key liquidglassEnabled true 2>/dev/null || true
              ok "Acrylic Glass installed (active after Plasma restart)"
            else
              warn "Acrylic Glass built but install failed (needs sudo)"
              info "Run manually:"
              echo "    sudo cp $_effect_so $_dest_effect"
              echo "    sudo cp $_config_so $_dest_config"
            fi
          fi
        else
          fail "Acrylic Glass build failed"
        fi
      else
        fail "Acrylic Glass cmake failed"
      fi
    fi
  fi
fi

# ── (future) Installing Sounds ───────────────────────────────
# ── (future) Installing GTK Theme ────────────────────────────
# ── (future) Installing SDDM Theme ───────────────────────────
# ── (future) Installing Custom Apps ──────────────────────────

# ── Applying Changes ─────────────────────────────────
step "Applying Changes"
note "Applies settings and tells KDE to reload"

# ── writing KDE config ──
if command -v kwriteconfig6 &>/dev/null; then
  if [[ "$(cfg fonts)" == "true" ]]; then
    kwriteconfig6 --file kdeglobals --group General --key font                 "SF Pro Text,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key menuFont             "SF Pro Text,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key toolBarFont          "SF Pro Text,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key taskbarFont          "SF Pro Text,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key smallestReadableFont "SF Pro Text,8,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group General --key fixed                "SF Mono,10,-1,5,50,0,0,0,0,0"
    kwriteconfig6 --file kdeglobals --group WM      --key activeFont           "SF Pro Display,11,-1,5,63,0,0,0,0,0"
    ok "Fonts installed"
  fi
fi
# icons, cursors, color scheme, plasma theme, kvantum, gtk
# are all applied by theme-switch.sh (auto light/dark based on time of day)

# ── applying themes (auto light/dark) ──
_switch_src="$OFFLINE/theme-switch.sh"
_switch_dest="$HOME/.local/bin/mac-tahoe-theme-switch"
_svc_src="$OFFLINE/mac-tahoe-liquid-kde-theme.service"
_svc_dest="$HOME/.config/systemd/user/mac-tahoe-liquid-kde-theme.service"

if [[ -f "$_switch_src" ]]; then
  mkdir -p "$HOME/.local/bin"
  cp -f "$_switch_src" "$_switch_dest"
  chmod +x "$_switch_dest"
fi
if [[ -f "$_svc_src" ]]; then
  mkdir -p "$HOME/.config/systemd/user"
  cp -f "$_svc_src" "$_svc_dest"
  systemctl --user daemon-reload 2>/dev/null || true
  if [[ "$_theme_mode" == "auto" ]]; then
    systemctl --user enable --now mac-tahoe-liquid-kde-theme.service &>/dev/null || true
  else
    # fixed mode — no need for the watcher service
    systemctl --user disable --now mac-tahoe-liquid-kde-theme.service &>/dev/null || true
  fi
fi
if [[ -x "$_switch_dest" ]]; then
  ok "Theme switcher installed"
  # NOTE: theme-switch is run AFTER Plasma restart to avoid heap corruption
  # from xsettingsd reloads arriving during Plasma init
else
  warn "Theme switcher not installed"
fi

# wallpaper (already has built-in auto light/dark via images + images_dark)
if [[ "$(cfg wallpapers)" == "true" ]]; then
  wp_path="$WALLPAPERS/MacTahoe"
  if [[ -d "$wp_path" ]] && command -v plasma-apply-wallpaperimage &>/dev/null; then
    plasma-apply-wallpaperimage "$wp_path" &>/dev/null || true
    ok "Wallpaper installed"
  fi
fi

# ── flushing caches ──
# ── restarting desktop ──
step "Restarting desktop"

note "Flushing icon, Plasma, and GTK caches"

# KDE icon caches
rm -rf "$HOME/.cache/icon-cache.kcache" 2>/dev/null || true
rm -rf "$HOME/.cache/kiconthemes" 2>/dev/null || true
rm -rf "$HOME/.cache/ksvg-elements" 2>/dev/null || true

# Plasma theme / SVG caches
rm -rf "$HOME/.cache/plasma-svgelements-"* 2>/dev/null || true
rm -rf "$HOME/.cache/plasma_theme_"* 2>/dev/null || true
rm -rf "$HOME/.cache/plasmashell"* 2>/dev/null || true

# sycoca
find "$HOME/.cache" -maxdepth 1 -name "ksycoca6*" -delete 2>/dev/null || true

# GTK caches
rm -rf "$HOME/.cache/gtk-3.0/" 2>/dev/null || true
rm -rf "$HOME/.cache/gtk-4.0/" 2>/dev/null || true

kbuildsycoca6 --noincremental 2>/dev/null || true
ok "Caches flushed"

# apply theme BEFORE restarting Plasma so everything is configured
if [[ -x "$_switch_dest" ]]; then
  "$_switch_dest" "$_theme_mode" &>/dev/null
  ok "Theme applied"
fi

if command -v nautilus &>/dev/null; then
  nautilus -q 2>/dev/null || true
  ok "Nautilus restarted"
fi

echo -ne "  …  Restarting KWin"
for qdbus_cmd in qdbus6 qdbus; do
  command -v "$qdbus_cmd" &>/dev/null && {
    if [[ "$(cfg acrylic_glass)" == "true" ]]; then
      "$qdbus_cmd" org.kde.KWin /Effects org.kde.kwin.Effects.loadEffect liquidglass &>/dev/null || true
    fi
    "$qdbus_cmd" org.kde.KWin /KWin org.kde.KWin.reconfigure &>/dev/null || true
    sleep 2
    break
  }
done
echo -e "\r  ${GREEN}✓${RESET}  KWin restarted "

# ── applying layout ──
if [[ "$(cfg layout)" == "true" ]]; then
  _layout="$REPO/src/offline/layouts/mac-tahoe.js"
  if [[ -f "$_layout" ]]; then
    _qdbus=""
    for _q in qdbus6 qdbus; do command -v "$_q" &>/dev/null && { _qdbus="$_q"; break; }; done
    if [[ -n "$_qdbus" ]]; then
      "$_qdbus" org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$(cat "$_layout")" &>/dev/null \
        && ok "Layout installed" \
        || warn "layout failed — set layout manually"
      sleep 3
      # patch plasmashellrc: JS scripting API doesn't expose panelOpacity or floatingApplets
      # panelOpacity: 0=adaptive, 1=opaque, 2=translucent
      _prc="$HOME/.config/plasmashellrc"
      if [[ -f "$_prc" ]]; then
        python3 -c "
import re, sys
text = open('$_prc').read()
def fix(m):
    section = m.group(0)
    # dock (floating=1): translucent opacity
    if 'floating=1' in section:
        if 'panelOpacity=' in section:
            section = re.sub(r'panelOpacity=\d+', 'panelOpacity=2', section)
        else:
            section = section.rstrip() + '\npanelOpacity=2\n'
    # top bar (floating=0): applets-only floating
    if 'floating=0' in section:
        if 'floatingApplets=' in section:
            section = re.sub(r'floatingApplets=\d+', 'floatingApplets=1', section)
        else:
            section = section.rstrip() + '\nfloatingApplets=1\n'
    return section
result = re.sub(r'(\[PlasmaViews\]\[Panel \d+\]\n(?:[^\[]*\n)*)', fix, text)
open('$_prc', 'w').write(result)
" 2>/dev/null && ok "Dock installed" || true
      fi
    else
      warn "qdbus not found — layout not installed"
    fi
  fi
fi

# restart plasma so everything loads clean (launchers, icons, dock)
echo -ne "  …  Restarting Plasma"
kquitapp6 plasmashell 2>/dev/null || killall plasmashell 2>/dev/null || true
for _i in $(seq 1 10); do pgrep -x plasmashell &>/dev/null || break; sleep 1; done
systemctl --user start plasma-plasmashell 2>/dev/null || kstart plasmashell 2>/dev/null &
for _i in $(seq 1 15); do pgrep -x plasmashell &>/dev/null && break; sleep 1; done
sleep 3
echo -e "\r  ${GREEN}✓${RESET}  Plasma restarted   "

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