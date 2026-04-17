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

# ── detect a usable session dbus once per shell ──
# --notify on kwriteconfig6 requires a live session bus; without it the
# call fails silently and the write gets dropped.  Detect at source time
# and cache so we don't pay the probe cost on every _kwrite.
if [[ -z "${_KWRITE_HAS_DBUS+x}" ]]; then
  if [[ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ]] \
     && command -v dbus-send &>/dev/null \
     && dbus-send --session --print-reply --dest=org.freedesktop.DBus \
          /org/freedesktop/DBus org.freedesktop.DBus.ListNames &>/dev/null; then
    _KWRITE_HAS_DBUS=1
  else
    _KWRITE_HAS_DBUS=0
  fi
fi

# ── write a single config key, serialised to avoid concurrent-write loss ──
# When kwriteconfig6 is invoked rapidly in succession on the same file,
# its atomic .tmp → rename sequence can race and silently drop writes.
# --notify adds a dbus round-trip that serialises them — but only works
# with a live session bus.  Fall back to plain kwriteconfig6 + sync
# elsewhere (TTY/ssh/systemd-run/sandboxed test contexts).
_kwrite() {
  if [[ "$_KWRITE_HAS_DBUS" == "1" ]]; then
    kwriteconfig6 --notify "$@"
  else
    kwriteconfig6 "$@"
  fi
  # Block until the tmp→rename is durable on disk — without this,
  # back-to-back callers race and silently drop writes.
  sync
}

# ── force-write [Colors:*]/[ColorEffects:*] groups from a .colors file ──
# plasma-apply-colorscheme is unreliable during install — it can silently
# fail and leave stale values from a previous scheme in kdeglobals. We
# parse the .colors file ourselves and write each group directly so the
# colour values always match the active ColorScheme name.
_apply_color_groups_direct() {
  local scheme="$1"
  command -v kwriteconfig6 &>/dev/null || return 1

  local scheme_file=""
  for dir in "$HOME/.local/share/color-schemes" "/usr/share/color-schemes"; do
    [[ -f "$dir/$scheme.colors" ]] && { scheme_file="$dir/$scheme.colors"; break; }
  done
  [[ -n "$scheme_file" ]] || return 1

  # Parse each [Colors:X] / [ColorEffects:X] section and write its keys
  local group=""
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    if [[ "$line" =~ ^\[(Colors:[^]]+|ColorEffects:[^]]+)\][[:space:]]*$ ]]; then
      group="${BASH_REMATCH[1]}"
    elif [[ "$line" =~ ^\[ ]]; then
      group=""   # Non-color section — stop writing
    elif [[ -n "$group" && "$line" =~ ^([^=]+)=(.*)$ ]]; then
      _kwrite --file kdeglobals --group "$group" \
        --key "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" 2>/dev/null || true
    fi
  done < "$scheme_file"
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

# ── read active mode from kdeglobals ColorScheme (authoritative KDE state) ──
# Preferred over the XDG portal because the portal backend can be stale right
# after install (install writes kdeglobals + gsettings but the portal may
# still report the previous mode until it refreshes).  Returns 1 if the
# active scheme isn't one of ours.
_current_theme_mode() {
  command -v kreadconfig6 &>/dev/null || return 1
  local scheme
  scheme=$(kreadconfig6 --file kdeglobals --group General --key ColorScheme 2>/dev/null)
  case "$scheme" in
    *Dark|*dark)   echo "dark"  ;;
    *Light|*light) echo "light" ;;
    *)             return 1     ;;
  esac
}

# ── detect current mode: kdeglobals → portal → time-of-day ──
# kdeglobals is authoritative (written atomically by install / theme-switch);
# portal is a secondary signal that can lag; time-of-day is last resort.
detect_mode() {
  local mode
  mode=$(_current_theme_mode) && [[ -n "$mode" ]] && { echo "$mode"; return; }
  local pref; pref=$(get_system_preference)
  if [[ "$pref" != "none" ]]; then echo "$pref"; else detect_mode_by_time; fi
}

# ── Plasma native auto mode ──
enable_auto_mode() {
  command -v kwriteconfig6 &>/dev/null || return 1
  _kwrite --file kdeglobals --group KDE --key AutomaticLookAndFeel true
  _kwrite --file kdeglobals --group KDE --key DefaultLightLookAndFeel "$LAF_LIGHT"
  _kwrite --file kdeglobals --group KDE --key DefaultDarkLookAndFeel "$LAF_DARK"
}

disable_auto_mode() {
  command -v kwriteconfig6 &>/dev/null || return 1
  _kwrite --file kdeglobals --group KDE --key AutomaticLookAndFeel false
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

# ── write all KDE config files for a given mode (no daemon calls) ──
# $1 = light|dark
# Writes: kdeglobals (ColorScheme + [Colors:*] groups + LookAndFeel + widgetStyle
#         + Icons), kcminputrc (cursor), plasmarc (plasma theme), kwinrc
#         (aurorae decoration).
# Used by both install ("install" context) and live theme-switch, so the
# resulting on-disk state is identical regardless of which entry point fired.
write_kde_theme_config() {
  local mode="$1"
  command -v kwriteconfig6 &>/dev/null || return 1

  local laf icon_theme cursor_theme color_scheme plasma_theme widget_style aurorae_theme
  if [[ "$mode" == "dark" ]]; then
    laf="$LAF_DARK"
    icon_theme="MacTahoeLiquidKde-Icons-dark"
    cursor_theme="MacTahoeLiquidKde-Dark"
    color_scheme="MacTahoeLiquidKdeDark"
    plasma_theme="MacTahoeLiquidKde-Dark"
    widget_style="kvantum-dark"
    aurorae_theme="__aurorae__svg__MacTahoeLiquidKde-Dark"
  else
    laf="$LAF_LIGHT"
    icon_theme="MacTahoeLiquidKde-Icons"
    cursor_theme="MacTahoeLiquidKde"
    color_scheme="MacTahoeLiquidKdeLight"
    plasma_theme="MacTahoeLiquidKde-Light"
    widget_style="kvantum"
    aurorae_theme="__aurorae__svg__MacTahoeLiquidKde-Light"
  fi

  # --notify forces kwriteconfig6 to flush before exiting; without it,
  # rapid back-to-back calls to the same file race and silently lose writes.
  _kwrite --file kdeglobals --group KDE     --key LookAndFeelPackage "$laf"
  _kwrite --file kdeglobals --group Icons   --key Theme               "$icon_theme"
  _kwrite --file kdeglobals --group General --key ColorScheme         "$color_scheme"
  _kwrite --file kdeglobals --group KDE     --key widgetStyle         "$widget_style"
  _kwrite --file kcminputrc --group Mouse   --key cursorTheme         "$cursor_theme"
  _kwrite --file plasmarc   --group Theme   --key name                "$plasma_theme"
  _kwrite --file kwinrc --group "org.kde.kdecoration2" --key library "org.kde.kwin.aurorae"
  _kwrite --file kwinrc --group "org.kde.kdecoration2" --key theme    "$aurorae_theme"
  _kwrite --file kwinrc --group "org.kde.kdecoration2" --key BorderSize     "Tiny"
  _kwrite --file kwinrc --group "org.kde.kdecoration2" --key ButtonsOnLeft  "XAI"
  _kwrite --file kwinrc --group "org.kde.kdecoration2" --key ButtonsOnRight ""

  # Copy the actual [Colors:*] / [ColorEffects:*] groups into kdeglobals.
  _apply_color_groups_direct "$color_scheme"
}

# ── apply all themes ──
# $1 = light|dark
# $2 = context: "boot" skips shell refresh, "install" skips plasma-apply-lookandfeel
#      (the installer restarts plasma at the end, which loads config from disk)
apply() {
  local mode="$1"
  local context="${2:-}"
  _errors=()

  local laf
  [[ "$mode" == "dark" ]] && laf="$LAF_DARK" || laf="$LAF_LIGHT"

  # Always write KDE config files (same path for install AND live switch —
  # guarantees identical on-disk state regardless of which entry point fired).
  write_kde_theme_config "$mode"

  if [[ "$context" == "install" ]]; then
    # Skip plasma-apply-lookandfeel during install — it triggers a QML engine
    # teardown race (SIGABRT in org.kde.panel.so).  The plasma restart at end
    # of install loads the on-disk config we just wrote.
    if command -v plasma-apply-colorscheme &>/dev/null; then
      local color_scheme
      [[ "$mode" == "dark" ]] && color_scheme="MacTahoeLiquidKdeDark" || color_scheme="MacTahoeLiquidKdeLight"
      plasma-apply-colorscheme "$color_scheme" &>/dev/null || true
    fi
  elif command -v plasma-apply-lookandfeel &>/dev/null; then
    plasma-apply-lookandfeel -a "$laf" --keep-auto &>/dev/null || _errors+=("global-theme")
  fi

  # ── extras (kvantum + gtk) — always apply, even during install
  apply_extras "$mode"

  # ── reconfigure kwin
  _qdbus org.kde.KWin /KWin org.kde.KWin.reconfigure &>/dev/null || true

  if [[ "$context" != "boot" && "$context" != "install" ]]; then
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
# Skip execution when sourced (e.g. by tests) so callers can use the
# helper functions without triggering disable_auto_mode / apply.
(return 0 2>/dev/null) && return 0

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
