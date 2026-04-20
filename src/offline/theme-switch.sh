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

# ── convert a KDE config section path into repeated --group args ──
# kwriteconfig6 expects nested groups to be passed as:
#   --group "Colors:Header" --group "Inactive"
# not as a single escaped string like "Colors:Header][Inactive".
_build_group_args() {
  local section="$1"
  local rest="$section"
  _GROUP_ARGS=()

  while [[ "$rest" =~ ^([^\[]+)\]\[(.+)$ ]]; do
    _GROUP_ARGS+=(--group "${BASH_REMATCH[1]}")
    rest="${BASH_REMATCH[2]}"
  done
  _GROUP_ARGS+=(--group "$rest")
}

# ── remove malformed escaped nested color groups left by older writers ──
# Older versions wrote nested sections like [Colors:Header][Inactive] as
# [Colors:Header\x5d\x5bInactive]. Clean those sections out before applying
# the correct palette so stale light/dark values cannot survive.
_scrub_malformed_color_groups() {
  local kdeglobals_path="${XDG_CONFIG_HOME:-$HOME/.config}/kdeglobals"
  [[ -f "$kdeglobals_path" ]] || return 0

  local tmp
  tmp=$(mktemp "${TMPDIR:-/tmp}/kdeglobals.XXXXXX") || return 1

  awk '
    /^\[(Colors:|ColorEffects:).*(\\x5d\\x5b).*\]$/ { skip=1; next }
    skip && /^\[/ { skip=0 }
    !skip { print }
  ' "$kdeglobals_path" > "$tmp" && mv "$tmp" "$kdeglobals_path"
}

# ── delete all explicit color keys from kdeglobals ──
# Used before rewriting a palette, and during uninstall when resetting to a
# system scheme such as BreezeLight. This leaves non-color settings intact.
_delete_color_groups_direct() {
  command -v kwriteconfig6 &>/dev/null || return 1

  local kdeglobals_path="${XDG_CONFIG_HOME:-$HOME/.config}/kdeglobals"
  [[ -f "$kdeglobals_path" ]] || return 0

  _scrub_malformed_color_groups || true

  while IFS=$'\t' read -r group key; do
    [[ -n "$group" && -n "$key" ]] || continue
    _build_group_args "$group"
    _kwrite --file kdeglobals "${_GROUP_ARGS[@]}" --key "$key" --delete 2>/dev/null || true
  done < <(
    awk '
      /^\[/{
        sec=$0
        sub(/^\[/, "", sec)
        sub(/\]$/, "", sec)
        next
      }
      sec ~ /^(Colors:|ColorEffects:|WM$)/ && /^[[:space:]]*[^#;[:space:]][^=]*=/ {
        key=$0
        sub(/[[:space:]]*=.*/, "", key)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
        if (length(key) > 0) print sec "\t" key
      }
    ' "$kdeglobals_path" | sort -u
  )
}

# ── reset kdeglobals to a named color scheme without leaving stale overrides ──
# This writes only the scheme name and removes explicit [Colors:*] / [WM] /
# [ColorEffects:*] overrides so KDE reloads the target scheme cleanly.
reset_kde_color_scheme_config() {
  local scheme="$1"
  command -v kwriteconfig6 &>/dev/null || return 1

  _delete_color_groups_direct || true
  _kwrite --file kdeglobals --group General --key ColorScheme "$scheme"
}

# ── force-write colour groups from a .colors file ──
# plasma-apply-colorscheme is unreliable during install — it can silently
# fail and leave stale values from a previous scheme in kdeglobals. We
# parse the .colors file ourselves and write each group directly so the
# colour values always match the active ColorScheme name.
# Includes:
#   [Colors:*], [ColorEffects:*], [WM]
# Also supports nested sections like [Colors:Header][Inactive].
_apply_color_groups_direct() {
  local scheme="$1"
  command -v kwriteconfig6 &>/dev/null || return 1

  local scheme_file=""
  for dir in "$HOME/.local/share/color-schemes" "/usr/share/color-schemes"; do
    [[ -f "$dir/$scheme.colors" ]] && { scheme_file="$dir/$scheme.colors"; break; }
  done
  [[ -n "$scheme_file" ]] || return 1

  local kdeglobals_path="${XDG_CONFIG_HOME:-$HOME/.config}/kdeglobals"

  # First remove old keys in all colour-related groups so stale values from a
  # previous scheme cannot survive when the new scheme omits a key.
  _delete_color_groups_direct || true

  # Parse colour-related groups and write each key
  local group="" key value section
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*([#;].*)?$ ]] && continue

    if [[ "$line" =~ ^\[(.+)\][[:space:]]*$ ]]; then
      section="${BASH_REMATCH[1]}"
      case "$section" in
        Colors:*|ColorEffects:*|WM) group="$section" ;;
        *)                          group="" ;;
      esac
    elif [[ -n "$group" && "$line" =~ ^([^=]+)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      value="${BASH_REMATCH[2]}"
      key="${key#"${key%%[![:space:]]*}"}"
      key="${key%"${key##*[![:space:]]}"}"
      _build_group_args "$group"
      _kwrite --file kdeglobals "${_GROUP_ARGS[@]}" \
        --key "$key" "$value" 2>/dev/null || true
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

# ── detect the target mode for auto-mode startup ──
# Auto is time-based and authoritative (6–18 light, else dark). The portal
# and kdeglobals can be stale or contradict us after a crash / external tool;
# ignore them for auto so the 11-AM dark-mode trap can't happen.
detect_auto_target_mode() {
  detect_mode_by_time
}

# ── auto mode (time-based, authoritative) ──
# We explicitly DISABLE Plasma's AutomaticLookAndFeel so the portal / KDE
# night-color scheduler can't override our 6–18 rule. Our timer + watch
# service are the only source of truth for auto.
enable_auto_mode() {
  command -v kwriteconfig6 &>/dev/null || return 1
  _kwrite --file kdeglobals --group KDE --key AutomaticLookAndFeel false
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
      gsettings set org.gnome.desktop.wm.preferences button-layout 'close,minimize,maximize:' &>/dev/null || true
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
  _kwrite --file kwinrc --group "org.kde.kdecoration2" --key ButtonsOnLeft  "XIA"
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
    # teardown race (SIGABRT in org.kde.panel.so). The Plasma restart at the
    # end of install loads the on-disk theme and color config we just wrote.
    :
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

# ── sync auto mode on session start ──
# If the user logs in after the scheduled light/dark transition, the last
# saved ColorScheme in kdeglobals can be stale. Compare the current saved
# mode against the current target mode and force a full apply only when they
# differ; otherwise just refresh the extras.
sync_auto_mode_on_startup() {
  local target_mode current_mode
  target_mode=$(detect_auto_target_mode)
  current_mode=$(_current_theme_mode 2>/dev/null || true)

  if [[ -n "$current_mode" && "$current_mode" == "$target_mode" ]]; then
    apply_extras "$target_mode"
  else
    apply "$target_mode" boot
  fi

  echo "$target_mode"
}

# ── watch mode: monitor dbus for color scheme changes ──
# Plasma's native autoswitcher drives the schedule; this applies
# Kvantum + GTK extras whenever the color scheme changes.
watch_loop() {
  wait_for_plasma || { echo "Plasma not ready after 60s, exiting" >&2; exit 1; }

  local last_mode; last_mode=$(sync_auto_mode_on_startup)

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
    # Auto = time-based, authoritative (6–18 light, else dark).
    # A systemd timer re-runs this at 06:00 and 18:00; the watch service
    # reacts to manual user overrides between transitions.
    apply "$(detect_mode_by_time)" "$_context"
    ;;
  watch) watch_loop ;;
  *)     echo "Usage: $0 {light|dark|auto|watch} [boot]" >&2; exit 1 ;;
esac
