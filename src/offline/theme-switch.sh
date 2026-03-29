#!/usr/bin/env bash
# MacTahoe Liquid KDE — Theme Switcher
# Switches all installed themes between light and dark variants.
#
# Usage:
#   theme-switch.sh light
#   theme-switch.sh dark
#   theme-switch.sh auto    (detect from system color scheme)
#   theme-switch.sh watch   (monitor dbus and auto-switch on change)

set -uo pipefail

ICONS_DIR="$HOME/.local/share/icons"

_mode="${1:-auto}"

# ── detect current system preference ──
detect_mode() {
  # KDE Plasma 6: read the freedesktop color-scheme portal setting
  # 1 = prefer dark, 2 = prefer light, 0 = no preference
  local val
  for qdbus_cmd in qdbus6 qdbus; do
    command -v "$qdbus_cmd" &>/dev/null || continue
    val=$("$qdbus_cmd" org.freedesktop.portal.Desktop \
      /org/freedesktop/portal/desktop \
      org.freedesktop.portal.Settings.Read \
      org.freedesktop.appearance color-scheme 2>/dev/null | grep -oP 'uint32 \K[0-9]+' || true)
    [[ -n "$val" ]] && break
  done

  # fallback: check kdeglobals ColorScheme name
  if [[ -z "$val" ]]; then
    local scheme
    scheme=$(grep -m1 'ColorScheme=' "$HOME/.config/kdeglobals" 2>/dev/null | cut -d= -f2)
    if [[ "$scheme" == *"Dark"* || "$scheme" == *"dark"* ]]; then
      val=1
    else
      val=2
    fi
  fi

  if [[ "$val" == "1" ]]; then
    echo "dark"
  else
    echo "light"
  fi
}

# ── apply themes ──
apply() {
  local mode="$1"

  # kvantum
  if command -v kvantummanager &>/dev/null; then
    if [[ "$mode" == "dark" ]]; then
      kvantummanager --set MacTahoeLiquidKdeDark &>/dev/null
    else
      kvantummanager --set MacTahoeLiquidKde &>/dev/null
    fi
  fi

  # icons
  if command -v plasma-apply-icontheme &>/dev/null; then
    if [[ "$mode" == "dark" ]]; then
      [[ -d "$ICONS_DIR/MacTahoeLiquidKde-Icons-dark" ]] && \
        plasma-apply-icontheme MacTahoeLiquidKde-Icons-dark &>/dev/null
    else
      [[ -d "$ICONS_DIR/MacTahoeLiquidKde-Icons" ]] && \
        plasma-apply-icontheme MacTahoeLiquidKde-Icons &>/dev/null
    fi
  fi

  # cursors
  if command -v plasma-apply-cursortheme &>/dev/null; then
    if [[ "$mode" == "dark" ]]; then
      [[ -d "$ICONS_DIR/MacTahoeLiquidKde-Dark/cursors" ]] && \
        plasma-apply-cursortheme MacTahoeLiquidKde-Dark &>/dev/null
    else
      [[ -d "$ICONS_DIR/MacTahoeLiquidKde/cursors" ]] && \
        plasma-apply-cursortheme MacTahoeLiquidKde &>/dev/null
    fi
  fi

  # color scheme
  if command -v plasma-apply-colorscheme &>/dev/null; then
    if [[ "$mode" == "dark" ]]; then
      plasma-apply-colorscheme BreezeDark &>/dev/null
    else
      plasma-apply-colorscheme BreezeLight &>/dev/null
    fi
  fi
}

# ── watch mode: monitor dbus for color scheme changes ──
watch_loop() {
  local last_mode
  last_mode=$(detect_mode)
  apply "$last_mode"

  dbus-monitor --session "type='signal',interface='org.freedesktop.portal.Settings',member='SettingChanged'" 2>/dev/null | \
  while read -r line; do
    if [[ "$line" == *"color-scheme"* ]]; then
      # small delay so KDE finishes applying its own change
      sleep 0.5
      local new_mode
      new_mode=$(detect_mode)
      if [[ "$new_mode" != "$last_mode" ]]; then
        apply "$new_mode"
        last_mode="$new_mode"
      fi
    fi
  done
}

# ── main ──
case "$_mode" in
  light) apply light ;;
  dark)  apply dark  ;;
  auto)  apply "$(detect_mode)" ;;
  watch) watch_loop ;;
  *)     echo "Usage: $0 {light|dark|auto|watch}" >&2; exit 1 ;;
esac
