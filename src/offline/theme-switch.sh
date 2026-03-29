#!/usr/bin/env bash
# MacTahoe Liquid KDE — Theme Switcher
# Switches all installed themes between light and dark variants.
# This is the single source of truth that links all theme components:
#
#   Color scheme    → MacTahoeLiquidKdeLight / MacTahoeLiquidKdeDark
#   Plasma theme    → MacTahoeLiquidKde-Light / MacTahoeLiquidKde-Dark
#   Kvantum         → mac-tahoe-liquid-kde / mac-tahoe-liquid-kdeDark
#   GTK             → MacTahoeLiquidKde-Light / MacTahoeLiquidKde-Dark
#   Icons           → MacTahoeLiquidKde-Icons / MacTahoeLiquidKde-Icons-dark
#   Cursors         → MacTahoeLiquidKde / MacTahoeLiquidKde-Dark
#
# Usage:
#   mac-tahoe-theme-switch light
#   mac-tahoe-theme-switch dark
#   mac-tahoe-theme-switch auto    (time of day: 7AM–7PM light, else dark)
#   mac-tahoe-theme-switch watch   (monitor dbus and auto-switch on change)

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
      QT_QPA_PLATFORM=offscreen kvantummanager --set mac-tahoe-liquid-kdeDark &>/dev/null
    else
      QT_QPA_PLATFORM=offscreen kvantummanager --set mac-tahoe-liquid-kde &>/dev/null
    fi
  fi

  # gtk
  local gtk_dest="$HOME/.themes"
  local gtk_theme
  if [[ "$mode" == "dark" ]]; then
    gtk_theme="MacTahoeLiquidKde-Dark"
  else
    gtk_theme="MacTahoeLiquidKde-Light"
  fi
  if [[ -d "$gtk_dest/$gtk_theme" ]]; then
    # 1. KDE GTK config daemon — sets GTK3 theme + triggers gtk-4.0 regeneration
    for _q in qdbus6 qdbus; do
      command -v "$_q" &>/dev/null && {
        "$_q" org.kde.GtkConfig /GtkConfig org.kde.GtkConfig.setGtkTheme "$gtk_theme" &>/dev/null || true
        break
      }
    done
    # 2. gsettings — color-scheme for libadwaita
    if command -v gsettings &>/dev/null; then
      gsettings set org.gnome.desktop.interface gtk-theme "$gtk_theme" &>/dev/null || true
      if [[ "$mode" == "dark" ]]; then
        gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark' &>/dev/null || true
      else
        gsettings set org.gnome.desktop.interface color-scheme 'prefer-light' &>/dev/null || true
      fi
    fi
    # 3. libadwaita/gtk4: overwrite ~/.config/gtk-4.0/ with compiled theme
    # wait for KDE's gtkconfig daemon to finish regenerating, then overwrite
    local gtk4_dest="$HOME/.config/gtk-4.0"
    local gtk4_src="$gtk_dest/$gtk_theme/gtk-4.0"
    if [[ -d "$gtk4_src" ]]; then
      (sleep 3 && \
       # stop portal before touching its files
       systemctl --user stop xdg-desktop-portal-gtk.service 2>/dev/null; \
       rm -rf "$gtk4_dest/assets" "$gtk4_dest/windows-assets" 2>/dev/null; \
       rm -f "$gtk4_dest/gtk.css" "$gtk4_dest/gtk-dark.css" "$gtk4_dest/gtk-Dark.css" "$gtk4_dest/gtk-Light.css" 2>/dev/null; \
       cp -rf "$gtk4_src/assets" "$gtk4_dest/" 2>/dev/null; \
       cp -rf "$gtk4_src/windows-assets" "$gtk4_dest/" 2>/dev/null; \
       cp -f "$gtk4_src/gtk-Dark.css" "$gtk4_dest/" 2>/dev/null; \
       cp -f "$gtk4_src/gtk-Light.css" "$gtk4_dest/" 2>/dev/null; \
       cd "$gtk4_dest" && \
       ln -sf "gtk-${mode^}.css" gtk.css 2>/dev/null; \
       ln -sf gtk-Dark.css gtk-dark.css 2>/dev/null; \
       # restart portal with new files
       systemctl --user start xdg-desktop-portal-gtk.service 2>/dev/null) &
    fi
  fi

  # icons
  local icon_theme
  if [[ "$mode" == "dark" ]]; then
    icon_theme="MacTahoeLiquidKde-Icons-dark"
  else
    icon_theme="MacTahoeLiquidKde-Icons"
  fi
  if [[ -d "$ICONS_DIR/$icon_theme" ]]; then
    if command -v plasma-apply-icontheme &>/dev/null; then
      plasma-apply-icontheme "$icon_theme" &>/dev/null
    elif command -v kwriteconfig6 &>/dev/null; then
      kwriteconfig6 --file kdeglobals --group Icons --key Theme "$icon_theme"
    fi
  fi

  # cursors
  local cursor_theme
  if [[ "$mode" == "dark" ]]; then
    cursor_theme="MacTahoeLiquidKde-Dark"
  else
    cursor_theme="MacTahoeLiquidKde"
  fi
  if [[ -d "$ICONS_DIR/$cursor_theme/cursors" ]]; then
    if command -v plasma-apply-cursortheme &>/dev/null; then
      plasma-apply-cursortheme "$cursor_theme" &>/dev/null
    elif command -v kwriteconfig6 &>/dev/null; then
      kwriteconfig6 --file kcminputrc --group Mouse --key cursorTheme "$cursor_theme"
    fi
  fi
}

# ── wait for plasma to be ready (display server + plasmashell) ──
wait_for_plasma() {
  local tries=0
  while [[ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] || ! pgrep -x plasmashell &>/dev/null; do
    sleep 2
    tries=$((tries + 1))
    [[ $tries -ge 30 ]] && return 1   # give up after 60s
    # re-import environment from systemd in case it was set after we started
    eval "$(systemctl --user show-environment 2>/dev/null | grep -E '^(DISPLAY|WAYLAND_DISPLAY)=')" 2>/dev/null || true
  done
  return 0
}

# ── watch mode: monitor dbus for color scheme changes ──
watch_loop() {
  wait_for_plasma || { echo "Plasma not ready after 60s, exiting" >&2; exit 1; }

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
