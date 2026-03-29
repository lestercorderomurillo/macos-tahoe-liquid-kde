#!/usr/bin/env bash
# MacTahoe Liquid KDE — Theme Switcher
# Switches all installed themes between light and dark variants.
# This is the single source of truth that links all theme components:
#
#   Color scheme    → MacTahoeLiquidKdeLight / MacTahoeLiquidKdeDark
#   Plasma theme    → MacTahoeLiquidKde-Light / MacTahoeLiquidKde-Dark
#   Kvantum         → MacTahoeLiquidKde / MacTahoeLiquidKdeDark
#   GTK             → MacTahoeLiquidKde-Light / MacTahoeLiquidKde-Dark
#   Icons           → MacTahoeLiquidKde-Icons / MacTahoeLiquidKde-Icons-dark
#   Cursors         → MacTahoeLiquidKde / MacTahoeLiquidKde-Dark
#
# Usage:
#   mactahoe-theme-switch light
#   mactahoe-theme-switch dark
#   mactahoe-theme-switch auto    (time of day: 7AM–7PM light, else dark)
#   mactahoe-theme-switch watch   (monitor dbus and auto-switch on change)

set -uo pipefail

ICONS_DIR="$HOME/.local/share/icons"

_mode="${1:-auto}"

# ── detect mode from time of day ──
detect_mode() {
  local hour
  hour=$(date +%H)
  if [[ $hour -ge 7 && $hour -lt 19 ]]; then
    echo "light"
  else
    echo "dark"
  fi
}

# ── apply all themes ──
apply() {
  local mode="$1"

  # color scheme
  if command -v plasma-apply-colorscheme &>/dev/null; then
    if [[ "$mode" == "dark" ]]; then
      plasma-apply-colorscheme MacTahoeLiquidKdeDark &>/dev/null || \
        plasma-apply-colorscheme BreezeDark &>/dev/null
    else
      plasma-apply-colorscheme MacTahoeLiquidKdeLight &>/dev/null || \
        plasma-apply-colorscheme BreezeLight &>/dev/null
    fi
  fi

  # plasma desktop theme
  if command -v kwriteconfig6 &>/dev/null; then
    local pt_dir="$HOME/.local/share/plasma/desktoptheme"
    if [[ "$mode" == "dark" ]]; then
      [[ -d "$pt_dir/MacTahoeLiquidKde-Dark" ]] && \
        kwriteconfig6 --file plasmarc --group Theme --key name MacTahoeLiquidKde-Dark 2>/dev/null
    else
      [[ -d "$pt_dir/MacTahoeLiquidKde-Light" ]] && \
        kwriteconfig6 --file plasmarc --group Theme --key name MacTahoeLiquidKde-Light 2>/dev/null
    fi
  fi

  # kvantum
  if command -v kvantummanager &>/dev/null; then
    if [[ "$mode" == "dark" ]]; then
      kvantummanager --set MacTahoeLiquidKdeDark &>/dev/null
    else
      kvantummanager --set MacTahoeLiquidKde &>/dev/null
    fi
  fi

  # gtk
  local gtk_dest="$HOME/.themes"
  local gtk4_dest="$HOME/.config/gtk-4.0"
  local gtk_theme
  if [[ "$mode" == "dark" ]]; then
    gtk_theme="MacTahoeLiquidKde-Dark"
  else
    gtk_theme="MacTahoeLiquidKde-Light"
  fi
  if [[ -d "$gtk_dest/$gtk_theme" ]]; then
    if command -v kwriteconfig6 &>/dev/null; then
      kwriteconfig6 --file kdeglobals --group KDE --key widgetStyle kvantum 2>/dev/null
    fi
    # gtk-3.0 settings
    mkdir -p "$HOME/.config/gtk-3.0"
    if [[ -f "$HOME/.config/gtk-3.0/settings.ini" ]]; then
      sed -i "s/^gtk-theme-name=.*/gtk-theme-name=$gtk_theme/" "$HOME/.config/gtk-3.0/settings.ini" 2>/dev/null || true
    else
      printf '[Settings]\ngtk-theme-name=%s\n' "$gtk_theme" > "$HOME/.config/gtk-3.0/settings.ini"
    fi
    # gtk-4.0 symlinks
    if [[ -d "$gtk_dest/$gtk_theme/gtk-4.0" ]]; then
      mkdir -p "$gtk4_dest"
      ln -sf "$gtk_dest/$gtk_theme/gtk-4.0/assets" "$gtk4_dest/assets" 2>/dev/null
      ln -sf "$gtk_dest/$gtk_theme/gtk-4.0/gtk.css" "$gtk4_dest/gtk.css" 2>/dev/null
      ln -sf "$gtk_dest/$gtk_theme/gtk-4.0/gtk-dark.css" "$gtk4_dest/gtk-dark.css" 2>/dev/null
    fi
    command -v gsettings &>/dev/null && gsettings set org.gnome.desktop.interface gtk-theme "$gtk_theme" &>/dev/null || true
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
}

# ── watch mode: monitor dbus for color scheme changes ──
watch_loop() {
  local last_mode
  last_mode=$(detect_mode)
  apply "$last_mode"

  dbus-monitor --session "type='signal',interface='org.freedesktop.portal.Settings',member='SettingChanged'" 2>/dev/null | \
  while read -r line; do
    if [[ "$line" == *"color-scheme"* ]]; then
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
