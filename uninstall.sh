#!/usr/bin/env bash
# MacTahoe Liquid KDE — Uninstaller
set -uo pipefail

_show_help() {
  cat <<'EOF'
Usage: bash uninstall.sh [OPTIONS]

Options:
  --help, -h           Show this help message and exit

  Feature flags (prefix with --no- to skip):
    --only             Disable all features first, then enable only those listed
    --wallpapers       Remove wallpaper collection
    --fonts            Remove SF Pro and SF Mono fonts
    --cursors          Remove macOS-style cursors
    --plasma-theme     Remove Plasma desktop theme
    --window-decorations  Remove Aurorae window decorations
    --kvantum          Remove Kvantum theme
    --color-schemes    Remove color schemes
    --icons            Remove icon themes
    --plasmoids        Remove custom Plasma widgets
    --acrylic-glass    Remove KWin blur effect
    --global-theme     Remove Plasma global theme
    --layout           Reset panel layout to default
    --sounds           Remove notification sounds
    --gtk              Remove GTK theme
    --sddm             Remove login screen theme
    --apps             Reset app configuration

Examples:
  bash uninstall.sh                     # uninstall everything
  bash uninstall.sh --icons --cursors   # only remove icons and cursors
EOF
}

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/src/steps/core.sh"
_parse_args "$@"
_apply_flags
_export_flags

[[ -d "$SRC" ]] || { echo -e "${RED}  Run from repo root.${RESET}" >&2; exit 1; }

_confirm "This will reset your desktop to Breeze defaults."

# ── Verification ─────────────────────────────────────────────────
step "Verification"
note "Checks KDE version"
_verify_plasma

# ── Uninstall features ───────────────────────────────────────────
#
# Execution order (design invariant — do not reorder):
#   1. Feature uninstall loop — removes files (layout skipped here)
#   2. Theme switcher         — stops and removes the switcher
#   3. Layout                 — resets panel layout (qdbus to running plasmashell)
#   4. Apply                  — resets to Breeze, flushes caches
#   5. Restart Plasma         — ALWAYS LAST

for _feature in "${_FEATURES[@]}"; do
  [[ "$_feature" == "layout" ]] && continue
  _should_process "$_feature" || continue

  _sf=$(step_file_for "$_feature")
  [[ -f "$_sf" ]] || continue

  _label="${_feature//_/ }"
  step "Removing ${_label}"
  note "${_FEAT_DESC[$_feature]:-}"
  run_step "$_sf" "uninstall"
done

# ── Theme Switcher ───────────────────────────────────────────────
step "Removing Theme Switcher"
note "Stops and removes the auto light/dark theme switcher"
run_step "$STEPS/theme-switch/step.sh" "uninstall"

# ── Layout ───────────────────────────────────────────────────────
if [[ "$(cfg layout)" == "true" ]] && [[ -f "$STEPS/layout/step.sh" ]]; then
  step "Resetting Layout"
  note "Resets panel layout to default"
  run_step "$STEPS/layout/step.sh" "uninstall"
fi

# ── Apply ────────────────────────────────────────────────────────
step "Applying Changes"
note "Resets to Breeze defaults and flushes caches"
run_step "$STEPS/apply/step.sh" "uninstall"

# ── Restart Plasma (always last) ─────────────────────────────────
step "Restarting Plasma"
note "Restarts Plasma shell to finalize changes"
run_step "$STEPS/apply/step.sh" "restart_plasma"

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
