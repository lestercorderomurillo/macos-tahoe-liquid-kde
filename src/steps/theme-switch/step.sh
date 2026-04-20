#!/usr/bin/env bash
# MacTahoe Liquid KDE — theme switcher installer step

SWITCH_SRC="$OFFLINE/theme-switch.sh"
SWITCH_DEST="$HOME/.local/bin/mac-tahoe-theme-switch"
SVC_DIR="$HOME/.config/systemd/user"

# unit file pairs: watch service (reacts to manual overrides) + timer + oneshot
# apply service (fires at 06:00 / 18:00). All three ship together so the
# 6–18 schedule is enforced even across reboots, suspends, and late logins.
UNITS=(
  mac-tahoe-liquid-kde-theme.service
  mac-tahoe-liquid-kde-theme.timer
  mac-tahoe-liquid-kde-theme-apply.service
)

install() {
  if [[ -f "$SWITCH_SRC" ]]; then
    mkdir -p "$HOME/.local/bin"
    cp -f "$SWITCH_SRC" "$SWITCH_DEST"
    chmod +x "$SWITCH_DEST"
  fi

  mkdir -p "$SVC_DIR"
  for u in "${UNITS[@]}"; do
    [[ -f "$OFFLINE/$u" ]] && cp -f "$OFFLINE/$u" "$SVC_DIR/$u"
  done
  systemctl --user daemon-reload 2>/dev/null || true

  if [[ "$THEME_MODE" == "auto" ]]; then
    systemctl --user enable --now mac-tahoe-liquid-kde-theme.service &>/dev/null || true
    systemctl --user enable --now mac-tahoe-liquid-kde-theme.timer   &>/dev/null || true
  else
    # explicit light/dark: user owns the preference, no scheduler
    systemctl --user disable --now mac-tahoe-liquid-kde-theme.service &>/dev/null || true
    systemctl --user disable --now mac-tahoe-liquid-kde-theme.timer   &>/dev/null || true
  fi

  if [[ -x "$SWITCH_DEST" ]]; then
    ok "Theme switcher installed"
  else
    warn "Theme switcher not installed"
  fi
}

uninstall() {
  for svc in mac-tahoe-liquid-kde-theme.service mac-tahoe-liquid-kde-theme.timer \
             mac-tahoe-liquid-kde-theme-apply.service mactahoe-theme-watcher.service; do
    systemctl --user disable --now "$svc" 2>/dev/null || true
    rm -f "$SVC_DIR/$svc" 2>/dev/null
  done
  systemctl --user daemon-reload 2>/dev/null || true
  rm -f "$HOME/.local/bin/mac-tahoe-theme-switch" "$HOME/.local/bin/mactahoe-theme-switch" 2>/dev/null
  # Disable Plasma native auto mode
  if command -v kwriteconfig6 &>/dev/null; then
    kw_write --file kdeglobals --group KDE --key AutomaticLookAndFeel false
    kw_write --file kdeglobals --group KDE --key DefaultLightLookAndFeel --delete 2>/dev/null || true
    kw_write --file kdeglobals --group KDE --key DefaultDarkLookAndFeel --delete 2>/dev/null || true
  fi
  ok "Theme switcher removed"
}
