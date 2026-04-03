#!/usr/bin/env bash
# MacTahoe Liquid KDE — theme switcher installer step

SWITCH_SRC="$OFFLINE/theme-switch.sh"
SWITCH_DEST="$HOME/.local/bin/mac-tahoe-theme-switch"
SVC_SRC="$OFFLINE/mac-tahoe-liquid-kde-theme.service"
SVC_DEST="$HOME/.config/systemd/user/mac-tahoe-liquid-kde-theme.service"

install() {
  if [[ -f "$SWITCH_SRC" ]]; then
    mkdir -p "$HOME/.local/bin"
    cp -f "$SWITCH_SRC" "$SWITCH_DEST"
    chmod +x "$SWITCH_DEST"
  fi
  if [[ -f "$SVC_SRC" ]]; then
    mkdir -p "$HOME/.config/systemd/user"
    cp -f "$SVC_SRC" "$SVC_DEST"
    systemctl --user daemon-reload 2>/dev/null || true
    if [[ "$THEME_MODE" == "auto" ]]; then
      systemctl --user enable --now mac-tahoe-liquid-kde-theme.service &>/dev/null || true
    else
      systemctl --user disable --now mac-tahoe-liquid-kde-theme.service &>/dev/null || true
    fi
  fi
  if [[ -x "$SWITCH_DEST" ]]; then
    ok "Theme switcher installed"
  else
    warn "Theme switcher not installed"
  fi
}

uninstall() {
  for svc in mac-tahoe-liquid-kde-theme.service mactahoe-theme-watcher.service; do
    systemctl --user disable --now "$svc" 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/$svc" 2>/dev/null
  done
  systemctl --user daemon-reload 2>/dev/null || true
  rm -f "$HOME/.local/bin/mac-tahoe-theme-switch" "$HOME/.local/bin/mactahoe-theme-switch" 2>/dev/null
  ok "Theme switcher removed"
}
