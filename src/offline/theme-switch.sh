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
#   mac-tahoe-theme-switch auto    (time of day: 6AM–6PM light, else dark)
#   mac-tahoe-theme-switch watch   (monitor dbus and auto-switch on change)

set -uo pipefail

ICONS_DIR="$HOME/.local/share/icons"

_mode="${1:-auto}"

# ── flush icon caches (safe for live desktop) ──
flush_icon_caches() {
  # only flush icon lookup caches — do NOT run kbuildsycoca6 or touch
  # plasmashell/plasma caches while the desktop is running, as that
  # causes the dock/task manager to rebuild and reorder pinned items
  rm -rf "$HOME/.cache/icon-cache.kcache" 2>/dev/null || true
  rm -rf "$HOME/.cache/kiconthemes" 2>/dev/null || true
}

# ── detect mode from time of day ──
detect_mode() {
  local hour
  hour=$(date +%H)
  if [[ $hour -ge 6 && $hour -lt 18 ]]; then
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
    # NOTE: runs synchronously to avoid race conditions with Plasma restart
    # NOTE: do NOT stop/start xdg-desktop-portal-gtk — it causes SEGV crashes
    local gtk4_dest="$HOME/.config/gtk-4.0"
    local gtk4_src="$gtk_dest/$gtk_theme/gtk-4.0"
    if [[ -d "$gtk4_src" ]]; then
      sleep 3
      mkdir -p "$gtk4_dest"
      cp -rf "$gtk4_src/assets" "$gtk4_dest/" 2>/dev/null
      cp -rf "$gtk4_src/windows-assets" "$gtk4_dest/" 2>/dev/null
      cp -f "$gtk4_src/gtk-Dark.css" "$gtk4_dest/" 2>/dev/null
      cp -f "$gtk4_src/gtk-Light.css" "$gtk4_dest/" 2>/dev/null
      ln -sf "gtk-${mode^}.css" "$gtk4_dest/gtk.css" 2>/dev/null
      ln -sf gtk-Dark.css "$gtk4_dest/gtk-dark.css" 2>/dev/null
    fi
  fi

  # icons — plasma-apply-icontheme does not exist in KDE 6,
  # so we write the config key and emit the dbus signal to notify all apps
  local icon_theme
  if [[ "$mode" == "dark" ]]; then
    icon_theme="MacTahoeLiquidKde-Icons-dark"
  else
    icon_theme="MacTahoeLiquidKde-Icons"
  fi
  if [[ -d "$ICONS_DIR/$icon_theme" ]] && command -v kwriteconfig6 &>/dev/null; then
    kwriteconfig6 --file kdeglobals --group Icons --key Theme "$icon_theme"
    # signal all KDE/Qt apps to reload icons
    dbus-send --session --type=signal /KIconLoader org.kde.KIconLoader.iconChanged int32:0 2>/dev/null || true
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

  # window decoration (aurorae)
  local au_theme
  if [[ "$mode" == "dark" ]]; then
    au_theme="MacTahoeLiquidKde-Dark"
  else
    au_theme="MacTahoeLiquidKde-Light"
  fi
  if [[ -d "$HOME/.local/share/aurorae/themes/$au_theme" ]] && command -v kwriteconfig6 &>/dev/null; then
    kwriteconfig6 --file kwinrc --group "org.kde.kdecoration2" --key "library" "org.kde.kwin.aurorae"
    kwriteconfig6 --file kwinrc --group "org.kde.kdecoration2" --key "theme" "__aurorae__svg__${au_theme}"
  fi

  # final cache rebuild + KWin reconfigure so dock/panel reflect new theme
  flush_icon_caches
  for _q in qdbus6 qdbus; do
    command -v "$_q" &>/dev/null && {
      "$_q" org.kde.KWin /KWin org.kde.KWin.reconfigure &>/dev/null || true
      break
    }
  done
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
