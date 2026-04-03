#!/usr/bin/env bash
# MacTahoe Liquid KDE — Installer
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
THEME_MODE=""
_do_save=false
_do_reset=false

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

for _arg in "$@"; do
  case "$_arg" in
    --light)       THEME_MODE="light" ;;
    --dark)        THEME_MODE="dark" ;;
    --auto)        THEME_MODE="auto" ;;
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
  "layout":              true,
  "sounds":              true,
  "gtk":                 true,
  "sddm":               true,
  "apps":                true,
  "no_download":         true,
  "theme_mode":          "auto"
}
DEFAULTS
  ok "features.json reset to defaults"
  for _f in "${_ALL_FEATURES[@]}"; do _feat[$_f]="$(_cfg_read "$_f")"; done
  THEME_MODE="auto"
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

cfg() { echo "${_feat[$1]:-true}"; }

NO_DOWNLOAD="${_feat[no_download]}"

# export feature flags for apply.sh
for _f in "${_ALL_FEATURES[@]}"; do
  _upper=$(echo "$_f" | tr '[:lower:]' '[:upper:]')
  export "FEAT_${_upper}=${_feat[$_f]}"
done
export THEME_MODE REPO SRC STEPS OFFLINE BUILD NO_DOWNLOAD

# ── step runner ──────────────────────────────────────────────────
# Sources one step file at a time in a subshell, calls the requested phase.
run_step() {
  local step_file="$1" phase="$2"
  (
    source "$STEPS/functions.sh"
    ERRORS=()  # subshell gets its own copy
    source "$step_file"
    if type -t "$phase" &>/dev/null; then
      "$phase"
    fi
    # propagate errors back via exit code
    [[ ${#ERRORS[@]} -eq 0 ]]
  ) || ERRORS+=("$(basename "$(dirname "$step_file")"): $phase failed")
}

# feature → step file mapping
step_file_for() {
  local feature="$1"
  local name="${feature//_/-}"
  echo "$STEPS/$name/step.sh"
}

[[ -d "$SRC" ]] || { echo -e "${RED}  Run from repo root.${RESET}" >&2; exit 1; }

# ── BETA WARNING ─────────────────────────────────────────────────
echo ""
echo -e "  ${RED}${BOLD}In development — Install at your own risk.${RESET}"
echo ""
read -p "  Continue? [Y/n] " _confirm
[[ "$_confirm" =~ ^[Nn]$ ]] && { echo "  Aborted."; exit 0; }
echo ""

sudo -v || { echo -e "  ${RED}sudo required.${RESET}"; exit 1; }

# ── Verification ─────────────────────────────────────────────────
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

# ── Dependencies ─────────────────────────────────────────────────
step "Dependencies"
note "Checking and installing required tools"

declare -A _deps_seen=()

_auto_dep_dedup() {
  local cmd="$1" pkg="${2:-$1}"
  [[ -n "${_deps_seen[$cmd]:-}" ]] && return 0
  _deps_seen[$cmd]=1
  auto_dep "$cmd" "$pkg"
}

_auto_dep_dedup curl
_auto_dep_dedup unzip
_auto_dep_dedup fc-cache fontconfig
_auto_dep_dedup kwriteconfig6 kconfig
_auto_dep_dedup cmake
_auto_dep_dedup g++ gcc
_auto_dep_dedup pkg-config pkgconf
_auto_dep_dedup dbus-monitor dbus

# ── single feature list (used for deps + install) ────────────────
# layout is here for deps but handled separately after apply (needs plasmashell)
# theme-switch and apply are always hardcoded at the end
_FEATURES=(wallpapers fonts cursors icons plasma_theme window_decorations kvantum color_schemes gtk plasmoids globalmenu acrylic_glass layout)

# step-specific deps
for _feature in "${_FEATURES[@]}"; do
  case "$_feature" in
    globalmenu) [[ "$(cfg plasmoids)" == "true" ]] || continue ;;
    *)          [[ "$(cfg "$_feature")" == "true" ]] || continue ;;
  esac
  _sf=$(step_file_for "$_feature")
  [[ -f "$_sf" ]] || continue
  while IFS= read -r dep; do
    [[ -z "$dep" ]] && continue
    _cmd="${dep%%:*}" _pkg="${dep#*:}"
    _auto_dep_dedup "$_cmd" "$_pkg"
  done < <(
    source "$STEPS/functions.sh"
    source "$_sf"
    type -t deps &>/dev/null && deps
  )
done

[[ -f "$CONFIG" ]] && ok "features.json loaded"

# ── check if a step defines a given function ─────────────────────
_step_has() {
  local sf="$1" fn="$2"
  ( source "$STEPS/functions.sh"; source "$sf"; type -t "$fn" &>/dev/null )
}

# should we skip download for this feature? (cache exists + no_download flag)
_has_cache() {
  local feature="$1"
  local cache="$STEPS/${feature//_/-}"
  [[ "$NO_DOWNLOAD" != "true" ]] && return 1
  case "$feature" in
    wallpapers) compgen -G "$cache/MacTahoe/contents/images/*" &>/dev/null ;;
    fonts)      compgen -G "$cache/*.otf" &>/dev/null ;;
    cursors)    [[ -d "$cache/MacTahoeLiquidKde/cursors" ]] ;;
    icons)      [[ -d "$cache/MacTahoeLiquidKde-Icons" ]] ;;
    *)          return 1 ;;
  esac
}

# ── Install features ─────────────────────────────────────────────
# One step per feature. Each step runs: download → build → install.
# Layout is skipped here — it runs after apply (needs plasmashell restarted).

for _feature in "${_FEATURES[@]}"; do
  # layout runs after apply, not here
  [[ "$_feature" == "layout" ]] && continue
  # globalmenu is gated by the plasmoids flag
  case "$_feature" in
    globalmenu) [[ "$(cfg plasmoids)" == "true" ]] || continue ;;
    *)          [[ "$(cfg "$_feature")" == "true" ]] || continue ;;
  esac

  _sf=$(step_file_for "$_feature")
  [[ -f "$_sf" ]] || continue

  _label="${_feature//_/ }"
  step "Installing ${_label}"
  case "$_feature" in
    wallpapers)          note "Downloads and installs macOS wallpaper packages" ;;
    fonts)               note "Downloads and installs SF Pro and SF Mono fonts" ;;
    cursors)             note "Downloads and installs MacTahoe cursor themes" ;;
    icons)               note "Downloads and installs MacTahoe icon themes" ;;
    plasma_theme)        note "Installs Plasma desktop theme (light and dark)" ;;
    window_decorations)  note "Installs macOS-style Aurorae window decorations" ;;
    kvantum)             note "Installs Kvantum Qt widget style theme" ;;
    color_schemes)       note "Installs color schemes (light and dark)" ;;
    gtk)                 note "Installs GTK theme for GNOME apps" ;;
    plasmoids)           note "Installs custom Plasma widgets" ;;
    globalmenu)          note "Builds and installs Global Menu C++ applet" ;;
    acrylic_glass)       note "Builds and installs Acrylic Glass KWin effect" ;;
  esac

  # download (skippable via --no-download when cache exists)
  if _step_has "$_sf" "download"; then
    if _has_cache "$_feature"; then
      ok "${_label} already downloaded"
    else
      run_step "$_sf" "download"
    fi
  fi

  # build (compile from source)
  if _step_has "$_sf" "build"; then
    run_step "$_sf" "build"
  fi

  # install
  run_step "$_sf" "install"
done

# ── Theme Switcher ───────────────────────────────────────────────
step "Installing Theme Switcher"
note "Installs the auto light/dark theme switcher"
run_step "$STEPS/theme-switch/step.sh" "install"

# ── Apply (config writes, cache flush, KWin restart — no plasma restart yet)
step "Applying Changes"
note "Applies settings, flushes caches, restarts KWin"
run_step "$STEPS/apply/step.sh" "install"

# ── Layout (after KWin restart, before plasma restart) ───────────
if [[ "$(cfg layout)" == "true" ]] && [[ -f "$STEPS/layout/step.sh" ]]; then
  step "Installing Layout"
  note "Applies panel layout and dock configuration"
  run_step "$STEPS/layout/step.sh" "install"
fi

# ── Restart Plasma (after layout is applied) ─────────────────────
step "Restarting Plasma"
note "Restarts Plasma shell to load all changes"
run_step "$STEPS/apply/step.sh" "restart_plasma"

# ── Done ─────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  ── Done${RESET}"
if [[ ${#ERRORS[@]} -eq 0 ]]; then
  ok "MacTahoe Liquid KDE installed successfully"
else
  warn "${#ERRORS[@]} issue(s) — everything else installed fine:"
  for e in "${ERRORS[@]}"; do fail "$e"; done
fi
echo ""
