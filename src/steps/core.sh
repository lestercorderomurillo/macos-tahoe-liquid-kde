#!/usr/bin/env bash
# MacTahoe Liquid KDE — shared installer/uninstaller core
# Sourced by install.sh and uninstall.sh — not run directly.

REPO="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
SRC="$REPO/src"
STEPS="$SRC/steps"
OFFLINE="$SRC/offline"
BUILD="$REPO/build"
CONFIG="$REPO/features.json"
VERSION_FILE="$REPO/VERSION"

source "$STEPS/functions.sh"

ERRORS=()
STEP=0
THEME_VERSION="0.0.0"
if [[ -f "$VERSION_FILE" ]]; then
  THEME_VERSION=$(tr -d '[:space:]' < "$VERSION_FILE")
fi
[[ "$THEME_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || THEME_VERSION="0.0.0"

step() {
  ((STEP++))
  echo ""
  echo -e "${GREEN}${BOLD}  Step ${STEP}: $*${RESET}"
}

_show_banner() {
  local line
  echo ""
  while IFS= read -r line; do
    echo -e "  ${RED}${BOLD}${line}${RESET}"
  done <<'EOF'
                   .:'
                 __ :'__
              .'`__`-'__`'.
             :__________.-'
             :_________:
              :_________`-;
               `.__.-.__.'
EOF
  echo ""
  echo -e "  ${GREEN}${BOLD}        MacTahoe Liquid KDE ${WHITE}v${THEME_VERSION}${RESET}"
  echo -e "  ${WHITE}            Developed by Lester${RESET}"
  echo ""
}

# ── feature flags ────────────────────────────────────────────────
_ALL_FEATURES=(wallpapers fonts cursors plasma_theme window_decorations kvantum color_schemes icons plasmoids acrylic_glass global_theme layout sounds gtk sddm apps nautilus no_download)

declare -A _feat=()
declare -A _cli=()
THEME_MODE=""
_do_save=false
_do_reset=false
_only_mode=false

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
THEME_MODE="$(_cfg_read "theme_mode")"
[[ "$THEME_MODE" =~ ^(auto|light|dark)$ ]] || THEME_MODE="auto"

# ── feature descriptions (shared between install and uninstall) ──
declare -A _FEAT_DESC=(
  [wallpapers]="macOS wallpaper collection"
  [fonts]="SF Pro and SF Mono typefaces"
  [cursors]="macOS-style cursors"
  [plasma_theme]="Plasma desktop theme (light and dark)"
  [window_decorations]="macOS-style Aurorae window decorations"
  [kvantum]="Kvantum Qt widget style theme"
  [color_schemes]="Color schemes (light and dark)"
  [icons]="macOS-style icon set"
  [plasmoids]="Custom Plasma widgets"
  [globalmenu]="Global Menu C++ applet"
  [acrylic_glass]="Acrylic Glass KWin blur effect"
  [global_theme]="Plasma global theme (look-and-feel)"
  [layout]="Panel layout (top bar + dock)"
  [sounds]="Notification and event sounds"
  [gtk]="GTK 2/3/4 theme"
  [sddm]="Login screen theme"
  [apps]="App configuration tweaks"
  [nautilus]="Nautilus file manager (default on KDE)"
)

# ── CLI parsing ──────────────────────────────────────────────────
_parse_args() {
  for _arg in "$@"; do
    case "$_arg" in
      -h|--help)     _show_help; exit 0 ;;
      --light)       THEME_MODE="light" ;;
      --dark)        THEME_MODE="dark" ;;
      --auto)        THEME_MODE="auto" ;;
      --only)        _only_mode=true ;;
      --save)        _do_save=true ;;
      --reset)       _do_reset=true ;;
      --no-download|--offline) _cli[no_download]="true" ;;
      --download)    _cli[no_download]="false" ;;
      --no-*)
        _key="${_arg#--no-}"; _key="${_key//-/_}"
        for _f in "${_ALL_FEATURES[@]}"; do [[ "$_f" == "$_key" ]] && { _cli[$_f]="false"; break; }; done
        ;;
      --*)
        _key="${_arg#--}"; _key="${_key//-/_}"
        for _f in "${_ALL_FEATURES[@]}"; do [[ "$_f" == "$_key" ]] && { _cli[$_f]="true"; break; }; done
        ;;
    esac
  done
}

_apply_flags() {
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
  "acrylic_glass":       true,
  "global_theme":        true,
  "layout":              true,
  "sounds":              true,
  "gtk":                 true,
  "sddm":               true,
  "apps":                true,
  "nautilus":            true,
  "no_download":         true,
  "theme_mode":          "auto"
}
DEFAULTS
    ok "features.json reset to defaults"
    for _f in "${_ALL_FEATURES[@]}"; do _feat[$_f]="$(_cfg_read "$_f")"; done
    THEME_MODE="auto"
  fi

  # --only: start from all-false, then only enable explicitly listed features
  if $_only_mode; then
    for _f in "${_ALL_FEATURES[@]}"; do
      [[ "$_f" == "no_download" ]] && continue
      _feat[$_f]="false"
    done
  fi

  for _f in "${_ALL_FEATURES[@]}"; do
    [[ -n "${_cli[$_f]:-}" ]] && _feat[$_f]="${_cli[$_f]}"
  done

  if $_do_save; then
    {
      echo "{"
      for _f in "${_ALL_FEATURES[@]}"; do
        printf '  "%-20s %s\n' "${_f}\":" "${_feat[$_f]},"
      done
      printf '  "%-20s "%s"\n' 'theme_mode":' "$THEME_MODE"
      echo "}"
    } > "$CONFIG"
    ok "features.json saved"
  fi
}

cfg() { echo "${_feat[$1]:-true}"; }

_export_flags() {
  NO_DOWNLOAD="${_feat[no_download]}"
  for _f in "${_ALL_FEATURES[@]}"; do
    _upper=$(echo "$_f" | tr '[:lower:]' '[:upper:]')
    export "FEAT_${_upper}=${_feat[$_f]}"
  done
  export THEME_MODE REPO SRC STEPS OFFLINE BUILD NO_DOWNLOAD
}

# ── step runner ──────────────────────────────────────────────────
run_step() {
  local step_file="$1" phase="$2"
  (
    source "$STEPS/functions.sh"
    ERRORS=()
    source "$step_file"
    if type -t "$phase" &>/dev/null; then
      "$phase"
    fi
    [[ ${#ERRORS[@]} -eq 0 ]]
  ) || ERRORS+=("$(basename "$(dirname "$step_file")"): $phase failed")
}

step_file_for() {
  local feature="$1"
  local name="${feature//_/-}"
  echo "$STEPS/$name/step.sh"
}

_step_has() {
  local sf="$1" fn="$2"
  ( source "$STEPS/functions.sh"; source "$sf"; type -t "$fn" &>/dev/null )
}

# ── verification ─────────────────────────────────────────────────
_verify_plasma() {
  if ! command -v plasmashell &>/dev/null; then
    fail "KDE Plasma not found"
    echo "     MacTahoe Liquid KDE requires KDE Plasma 6.6+."
    exit 1
  fi

  plasma_ver=$(plasmashell --version 2>/dev/null | grep -oP '[0-9]+[.][0-9]+[.][0-9]+' | head -1)
  plasma_major=$(echo "$plasma_ver" | cut -d. -f1)
  plasma_minor=$(echo "$plasma_ver" | cut -d. -f2)

  if [[ "$plasma_major" -lt 6 ]] || { [[ "$plasma_major" -eq 6 ]] && [[ "$plasma_minor" -lt 6 ]]; }; then
    fail "KDE Plasma $plasma_ver (6.6+ required)"
    exit 1
  fi

  ok "KDE Plasma $plasma_ver"
  [[ -f "$CONFIG" ]] && ok "features.json loaded"
}

# ── confirm prompt ───────────────────────────────────────────────
_confirm() {
  local msg="$1"
  echo ""
  echo -e "  ${RED}${BOLD}${msg}${RESET}"
  echo ""
  read -p "  Continue? [Y/n] " _c
  [[ "$_c" =~ ^[Nn]$ ]] && { echo "  Aborted."; exit 0; }
  echo ""
  sudo -v || { echo -e "  ${RED}sudo required.${RESET}"; exit 1; }
}

# ── feature list for install/uninstall loop ──────────────────────
_FEATURES=(wallpapers fonts cursors icons plasma_theme window_decorations kvantum color_schemes gtk plasmoids globalmenu acrylic_glass global_theme layout nautilus)

# ── should feature be processed? ─────────────────────────────────
_should_process() {
  local f="$1"
  case "$f" in
    globalmenu) [[ "$(cfg plasmoids)" == "true" ]] ;;
    *)          [[ "$(cfg "$f")" == "true" ]] ;;
  esac
}
