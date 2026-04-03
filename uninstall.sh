#!/usr/bin/env bash
# MacTahoe Liquid KDE — Uninstaller
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO/src"
STEPS="$SRC/steps"
OFFLINE="$SRC/offline"
BUILD="$REPO/build"
CONFIG="$REPO/features.json"

source "$STEPS/functions.sh"

ERRORS=()
STEP=0

step() {
  ((STEP++))
  echo ""
  echo -e "${GREEN}${BOLD}  Step ${STEP}: $*${RESET}"
}

# ── feature flags ────────────────────────────────────────────────
_ALL_FEATURES=(wallpapers fonts cursors plasma_theme window_decorations kvantum color_schemes icons plasmoids acrylic_glass layout sounds gtk sddm apps no_download)
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
      _key="${_arg#--no-}"; _key="${_key//-/_}"
      for _f in "${_ALL_FEATURES[@]}"; do [[ "$_f" == "$_key" ]] && { _cli[$_f]="false"; break; }; done
      ;;
    --*)
      _key="${_arg#--}"; _key="${_key//-/_}"
      for _f in "${_ALL_FEATURES[@]}"; do [[ "$_f" == "$_key" ]] && { _cli[$_f]="true"; break; }; done
      ;;
  esac
done

for _f in "${_ALL_FEATURES[@]}"; do
  [[ -n "${_cli[$_f]:-}" ]] && _feat[$_f]="${_cli[$_f]}"
done

cfg() { echo "${_feat[$1]:-true}"; }

# export feature flags for apply.sh
THEME_MODE="auto"
for _f in "${_ALL_FEATURES[@]}"; do
  _upper=$(echo "$_f" | tr '[:lower:]' '[:upper:]')
  export "FEAT_${_upper}=${_feat[$_f]}"
done
export THEME_MODE REPO SRC STEPS OFFLINE BUILD

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

[[ -d "$REPO/src" ]] || { echo -e "${RED}  Run from repo root.${RESET}" >&2; exit 1; }

# ── confirm ──────────────────────────────────────────────────────
echo ""
echo -e "  ${RED}${BOLD}This will reset your desktop to Breeze defaults.${RESET}"
echo ""
read -p "  Continue? [Y/n] " _confirm
[[ "$_confirm" =~ ^[Nn]$ ]] && { echo "  Aborted."; exit 0; }
echo ""

sudo -v || { echo -e "  ${RED}sudo required.${RESET}"; exit 1; }

# ── Verification ─────────────────────────────────────────────────
step "Verification"
note "Checks KDE version"

if ! command -v plasmashell &>/dev/null; then
  fail "KDE Plasma not found"; exit 1
fi

plasma_ver=$(plasmashell --version 2>/dev/null | grep -oP '[0-9]+[.][0-9]+[.][0-9]+' | head -1)
ok "KDE Plasma $plasma_ver"
[[ -f "$CONFIG" ]] && ok "features.json loaded"

# ── Uninstall each feature ───────────────────────────────────────
_FEATURES=(wallpapers fonts cursors icons plasmoids globalmenu acrylic_glass plasma_theme window_decorations kvantum color_schemes gtk layout)

for _feature in "${_FEATURES[@]}"; do
  case "$_feature" in
    globalmenu) [[ "$(cfg plasmoids)" == "true" ]] || continue ;;
    *)          [[ "$(cfg "$_feature")" == "true" ]] || continue ;;
  esac

  _sf=$(step_file_for "$_feature")
  [[ -f "$_sf" ]] || continue

  _label="${_feature//_/ }"
  step "Removing ${_label}"
  case "$_feature" in
    wallpapers)          note "Removes all MacTahoe wallpaper packages" ;;
    fonts)               note "Removes SF Pro and SF Mono font files" ;;
    cursors)             note "Removes MacTahoe cursor themes" ;;
    icons)               note "Removes MacTahoe icon themes" ;;
    plasmoids)           note "Removes custom Plasma widgets" ;;
    globalmenu)          note "Removes Global Menu C++ applet" ;;
    acrylic_glass)       note "Unloads and removes Acrylic Glass KWin effect" ;;
    plasma_theme)        note "Removes Plasma desktop theme and resets to Breeze" ;;
    window_decorations)  note "Removes Aurorae window decorations and resets to Breeze" ;;
    kvantum)             note "Removes Kvantum theme (keeps Kvantum installed)" ;;
    color_schemes)       note "Removes color schemes (light and dark)" ;;
    gtk)                 note "Removes GTK themes for GNOME apps" ;;
    layout)              note "Resets panel layout to default" ;;
  esac
  run_step "$_sf" "uninstall"
done

# ── Theme Switcher ───────────────────────────────────────────────
step "Removing Theme Switcher"
note "Stops and removes the auto light/dark theme switcher"
run_step "$STEPS/theme-switch/step.sh" "uninstall"

# ── Apply (reset to Breeze, flush caches, restart) ───────────────
step "Applying Changes"
note "Resets to Breeze defaults and restarts Plasma"
run_step "$STEPS/apply/step.sh" "uninstall"

# ── Done ─────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  ── Done${RESET}"
if [[ ${#ERRORS[@]} -eq 0 ]]; then
  ok "MacTahoe Liquid KDE uninstalled successfully"
else
  warn "${#ERRORS[@]} issue(s):"
  for e in "${ERRORS[@]}"; do fail "$e"; done
fi
echo ""
