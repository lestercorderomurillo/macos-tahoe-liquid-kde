#!/usr/bin/env bash
# MacTahoe Liquid KDE — Theme Switcher
#
# Plasma 6 native autoswitcher (lookandfeelautoswitcher KDED module) handles:
#   color scheme, plasma theme, icons, cursors, aurorae, wallpaper
#
# This script manages what Plasma does NOT switch automatically:
#   Kvantum, GTK 2/3/4, icon/theme caches
#
# For explicit light/dark, it also calls plasma-apply-lookandfeel.
# For watch mode, it lets Plasma drive the schedule and only handles extras.
#
# Usage:
#   mac-tahoe-theme-switch light       # force light (disables auto)
#   mac-tahoe-theme-switch dark        # force dark (disables auto)
#   mac-tahoe-theme-switch auto        # enable Plasma auto, apply current mode
#   mac-tahoe-theme-switch watch       # monitor dbus, apply extras on change

set -uo pipefail

_mode="${1:-auto}"
_context="${2:-}"
_errors=()

# ── global theme IDs ──
LAF_LIGHT="org.kde.mac-tahoe-liquid-kde.light"
LAF_DARK="org.kde.mac-tahoe-liquid-kde.dark"

# ── qdbus wrapper ──
_qdbus() {
  for _q in qdbus6 qdbus; do
    command -v "$_q" &>/dev/null && { "$_q" "$@"; return; }
  done
  return 1
}

# ── flush icon caches (safe for live desktop) ──
flush_icon_caches() {
  rm -rf "$HOME/.cache/icon-cache.kcache" 2>/dev/null || true
  rm -rf "$HOME/.cache/kiconthemes" 2>/dev/null || true
}

# ── detect mode from time of day (fallback) ──
detect_mode_by_time() {
  local hour; hour=$(date +%H)
  if [[ $hour -ge 6 && $hour -lt 18 ]]; then echo "light"; else echo "dark"; fi
}

# ── read system color-scheme preference via xdg portal ──
get_system_preference() {
  local reply
  reply=$(dbus-send --session --print-reply \
    --dest=org.freedesktop.portal.Desktop \
    /org/freedesktop/portal/desktop \
    org.freedesktop.portal.Settings.Read \
    string:"org.freedesktop.appearance" string:"color-scheme" 2>/dev/null) || {
    echo "none"; return
  }
  # Portal color-scheme: 0 = no preference, 1 = prefer-dark, 2 = prefer-light
  if echo "$reply" | grep -q "uint32 1"; then echo "dark"
  elif echo "$reply" | grep -q "uint32 2"; then echo "light"
  else echo "none"
  fi
}

# ── detect current mode: portal first, time-of-day fallback ──
detect_mode() {
  local pref; pref=$(get_system_preference)
  if [[ "$pref" != "none" ]]; then echo "$pref"; else detect_mode_by_time; fi
}

# ── Plasma native auto mode ──
enable_auto_mode() {
  command -v kwriteconfig6 &>/dev/null || return 1
  kwriteconfig6 --file kdeglobals --group KDE --key AutomaticLookAndFeel true
  kwriteconfig6 --file kdeglobals --group KDE --key DefaultLightLookAndFeel "$LAF_LIGHT"
  kwriteconfig6 --file kdeglobals --group KDE --key DefaultDarkLookAndFeel "$LAF_DARK"
}

disable_auto_mode() {
  command -v kwriteconfig6 &>/dev/null || return 1
  kwriteconfig6 --file kdeglobals --group KDE --key AutomaticLookAndFeel false
}

# ── apply extras only (Kvantum + GTK) ──
# Plasma's global theme handles the rest; this covers what it skips.
apply_extras() {
  local mode="$1"

  # ── kvantum
  if command -v kvantummanager &>/dev/null; then
    local kv_theme
    [[ "$mode" == "dark" ]] && kv_theme="mac-tahoe-liquid-kdeDark" || kv_theme="mac-tahoe-liquid-kde"
    QT_QPA_PLATFORM=offscreen kvantummanager --set "$kv_theme" &>/dev/null || true
  fi

  # ── gtk
  local gtk_dest="$HOME/.themes"
  local gtk_theme
  [[ "$mode" == "dark" ]] && gtk_theme="MacTahoeLiquidKde-Dark" || gtk_theme="MacTahoeLiquidKde-Light"
  if [[ -d "$gtk_dest/$gtk_theme" ]]; then
    _qdbus org.kde.GtkConfig /GtkConfig org.kde.GtkConfig.setGtkTheme "$gtk_theme" &>/dev/null || true
    if command -v gsettings &>/dev/null; then
      gsettings set org.gnome.desktop.interface gtk-theme "$gtk_theme" &>/dev/null || true
      if [[ "$mode" == "dark" ]]; then
        gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark' &>/dev/null || true
      else
        gsettings set org.gnome.desktop.interface color-scheme 'prefer-light' &>/dev/null || true
      fi
    fi
    # gtk4: overwrite ~/.config/gtk-4.0/ with theme CSS
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

  # ── flush caches
  flush_icon_caches
  rm -f "$HOME/.cache/ksvg-elements" 2>/dev/null || true
  rm -f "$HOME/.cache"/plasma_theme_* 2>/dev/null || true
}

# ── apply all themes ──
# $1 = light|dark
# $2 = "boot" to skip shell refresh
apply() {
  local mode="$1"
  local context="${2:-}"
  _errors=()

  # ── global theme (color scheme, plasma theme, icons, cursors, aurorae, wallpaper)
  if command -v plasma-apply-lookandfeel &>/dev/null; then
    local laf
    [[ "$mode" == "dark" ]] && laf="$LAF_DARK" || laf="$LAF_LIGHT"
    plasma-apply-lookandfeel -a "$laf" --keep-auto &>/dev/null || _errors+=("global-theme")
  fi

  # ── extras (kvantum + gtk)
  apply_extras "$mode"

  # ── reconfigure kwin
  _qdbus org.kde.KWin /KWin org.kde.KWin.reconfigure &>/dev/null || true

  if [[ "$context" != "boot" ]]; then
    _qdbus org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.refreshCurrentShell &>/dev/null || true
  fi

  if [[ ${#_errors[@]} -gt 0 ]]; then
    echo "theme-switch: failed components: ${_errors[*]}" >&2
    return 1
  fi
}

# ── wait for plasma to be ready ──
wait_for_plasma() {
  local tries=0
  while [[ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] || ! pgrep -x plasmashell &>/dev/null; do
    sleep 2; tries=$((tries + 1))
    [[ $tries -ge 30 ]] && return 1
    eval "$(systemctl --user show-environment 2>/dev/null | grep -E '^(DISPLAY|WAYLAND_DISPLAY)=')" 2>/dev/null || true
  done
  local kd=0
  while ! pgrep -x kded6 &>/dev/null; do
    sleep 1; kd=$((kd + 1)); [[ $kd -ge 20 ]] && break
  done
  sleep 3
  return 0
}

# ── watch mode: monitor dbus for color scheme changes ──
# Plasma's native autoswitcher drives the schedule; this applies
# Kvantum + GTK extras whenever the color scheme changes.
watch_loop() {
  wait_for_plasma || { echo "Plasma not ready after 60s, exiting" >&2; exit 1; }

  local last_mode; last_mode=$(detect_mode)
  apply_extras "$last_mode"

  dbus-monitor --session "type='signal',interface='org.freedesktop.portal.Settings',member='SettingChanged'" 2>/dev/null | \
  while read -r line; do
    if [[ "$line" == *"color-scheme"* ]]; then
      sleep 0.5
      local new_mode; new_mode=$(detect_mode)
      if [[ "$new_mode" != "$last_mode" ]]; then
        apply_extras "$new_mode"
        last_mode="$new_mode"
      fi
    fi
  done
}

# ── main ──
case "$_mode" in
  light)
    disable_auto_mode
    apply light "$_context"
    ;;
  dark)
    disable_auto_mode
    apply dark "$_context"
    ;;
  auto)
    enable_auto_mode
    # No preference — let the schedule decide. Plasma's autoswitcher takes
    # over from here; time-of-day is a close-enough initial approximation.
    apply "$(detect_mode_by_time)" "$_context"
    ;;
  watch) watch_loop ;;
  *)     echo "Usage: $0 {light|dark|auto|watch} [boot]" >&2; exit 1 ;;
esac
