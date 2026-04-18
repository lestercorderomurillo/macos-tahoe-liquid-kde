#!/usr/bin/env bash
# MacTahoe Liquid KDE — Installer
set -uo pipefail

_show_help() {
  cat <<'EOF'
Usage: bash install.sh [OPTIONS]

Options:
  --help, -h           Show this help message and exit

  Theme mode:
    --light            Force light theme
    --dark             Force dark theme
    --auto             Automatic switching via sunrise/sunset (default)

  Feature flags (prefix with --no- to disable):
    --only             Disable all features first, then enable only those listed
    --wallpapers       macOS wallpaper collection
    --fonts            SF Pro and SF Mono typefaces
    --cursors          macOS-style cursors
    --plasma-theme     Translucent panels and dock
    --window-decorations  Aurorae window title bars
    --kvantum          Kvantum Qt widget style
    --color-schemes    Light and Dark palettes
    --icons            macOS-style icon set
    --plasmoids        Custom Plasma widgets (Menu, Launcher, Trashcan)
    --acrylic-glass    KWin blur + rounded corners effect
    --global-theme     Plasma global theme (look-and-feel package)
    --layout           Panel layout (top bar + dock)
    --sounds           Notification and event sounds
    --gtk              GTK 2/3/4 theme
    --sddm             Login screen theme
    --apps             App configuration tweaks
    --nautilus         Install Nautilus and set as default file manager
    --no-download      Skip downloads, use cached assets

  Persistence:
    --save             Save current flags to features.json
    --reset            Reset features.json to all-true defaults

Examples:
  bash install.sh                             # install everything
  bash install.sh --no-gtk --no-sddm          # skip GTK and SDDM
  bash install.sh --only --fonts --icons      # install only fonts and icons
  bash install.sh --dark --save               # dark mode, remember setting
  bash install.sh --reset                     # restore defaults
EOF
}

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/src/steps/core.sh"
_parse_args "$@"
_apply_flags
_export_flags

[[ -d "$SRC" ]] || { echo -e "${RED}  Run from repo root.${RESET}" >&2; exit 1; }

_show_banner
_confirm "In development — Install at your own risk."

# ── Verification ─────────────────────────────────────────────────
step "Verification"
note "Checks KDE version and required tools"
_verify_plasma

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

for _feature in "${_FEATURES[@]}"; do
  _should_process "$_feature" || continue
  _sf=$(step_file_for "$_feature")
  [[ -f "$_sf" ]] || continue
  while IFS= read -r dep; do
    [[ -z "$dep" ]] && continue
    _cmd="${dep%%:*}" _pkg="${dep#*:}"
    _auto_dep_dedup "$_cmd" "$_pkg"
  done < <(source "$STEPS/functions.sh"; source "$_sf"; type -t deps &>/dev/null && deps)
done

# should we skip download? (cache exists + no_download flag)
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
#
# Execution order (design invariant — do not reorder):
#   1. Feature install loop  — installs files, builds C++ applets
#   2. Theme switcher        — installs the light/dark switcher
#   3. Apply                 — writes KDE config, flushes caches, restarts KWin
#   4. Layout                — applies panel layout (qdbus to running plasmashell)
#   5. Restart Plasma        — ALWAYS LAST

for _feature in "${_FEATURES[@]}"; do
  [[ "$_feature" == "layout" ]] && continue
  _should_process "$_feature" || continue

  _sf=$(step_file_for "$_feature")
  [[ -f "$_sf" ]] || continue

  _label="${_feature//_/ }"
  step "Installing ${_label}"
  note "${_FEAT_DESC[$_feature]:-}"

  if _step_has "$_sf" "download"; then
    if _has_cache "$_feature"; then
      ok "${_label} already downloaded"
    else
      run_step "$_sf" "download"
    fi
  fi
  _step_has "$_sf" "build" && run_step "$_sf" "build"
  run_step "$_sf" "install"
done

# ── Theme Switcher ───────────────────────────────────────────────
step "Installing Theme Switcher"
note "Installs the auto light/dark theme switcher"
run_step "$STEPS/theme-switch/step.sh" "install"

# ── Apply ────────────────────────────────────────────────────────
step "Applying Changes"
note "Applies settings, flushes caches, restarts KWin"
run_step "$STEPS/apply/step.sh" "install"

# ── Layout ───────────────────────────────────────────────────────
if [[ "$(cfg layout)" == "true" ]] && [[ -f "$STEPS/layout/step.sh" ]]; then
  step "Installing Layout"
  note "${_FEAT_DESC[layout]}"
  run_step "$STEPS/layout/step.sh" "install"
fi

# ── Apply theme live (after layout, before restart) ─────────────
rm -rf "$HOME/.cache/icon-cache.kcache" "$HOME/.cache/kiconthemes" 2>/dev/null || true
dbus-send --session --type=signal /KIconLoader org.kde.KIconLoader.iconChanged int32:0 2>/dev/null || true

# ── Verify config ────────────────────────────────────────────────
step "Verification"
note "Checking theme configuration was applied"
_verify_config() {
  local file="$1" group="$2" key="$3" expected="$4" label="$5"
  local actual
  actual=$(kreadconfig6 --file "$file" --group "$group" --key "$key" 2>/dev/null)
  if [[ "$actual" == *"$expected"* ]]; then
    ok "$label"
  else
    fail "$label (expected $expected, got ${actual:-empty})"
  fi
}
if [[ "$(cfg icons)" == "true" ]]; then
  _verify_config kdeglobals Icons Theme "MacTahoeLiquidKde-Icons" "Icon theme"
fi
if [[ "$(cfg color_schemes)" == "true" ]]; then
  _verify_config kdeglobals General ColorScheme "MacTahoeLiquidKde" "Color scheme"
fi
if [[ "$(cfg cursors)" == "true" ]]; then
  _verify_config kcminputrc Mouse cursorTheme "MacTahoeLiquidKde" "Cursor theme"
fi
if [[ "$(cfg plasma_theme)" == "true" ]]; then
  _verify_config plasmarc Theme name "MacTahoeLiquidKde" "Plasma theme"
fi
if [[ "$(cfg window_decorations)" == "true" ]]; then
  _verify_config kwinrc "org.kde.kdecoration2" theme "__aurorae__svg__MacTahoeLiquidKde" "Window decorations"
fi

# ── Restart Plasma (always last) ─────────────────────────────────
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
