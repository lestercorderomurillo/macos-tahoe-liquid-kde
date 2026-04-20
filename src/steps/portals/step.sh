#!/usr/bin/env bash
# MacTahoe Liquid KDE — xdg-desktop-portal routing step
#
# Forces FileChooser / AppChooser to the KDE backend so "Open with…" and
# file pickers render as native Qt/KDE dialogs (not the GTK/Nautilus one).
# The GTK portal loads its CSS once at process start and does not reload
# on theme change, so dark/light transitions leave the dialog stale until
# logout — routing to KDE sidesteps that entirely.

CONF_DIR="$HOME/.config/xdg-desktop-portal"
CONF_FILE="$CONF_DIR/kde-portals.conf"

install() {
  mkdir -p "$CONF_DIR"
  cat > "$CONF_FILE" <<'EOF'
[preferred]
default=kde
org.freedesktop.impl.portal.FileChooser=kde
org.freedesktop.impl.portal.AppChooser=kde
EOF
  if [[ -f "$CONF_FILE" ]]; then
    ok "KDE portal routing installed"
  else
    fail "KDE portal routing"
    return 1
  fi

  # Bounce portal services so the new routing takes effect without logout.
  # Ignore errors — some services may not exist on minimal installs.
  if command -v systemctl &>/dev/null; then
    for svc in xdg-desktop-portal xdg-desktop-portal-kde xdg-desktop-portal-gtk; do
      systemctl --user restart "$svc" 2>/dev/null || true
    done
  fi
}

uninstall() {
  if [[ -f "$CONF_FILE" ]]; then
    rm -f "$CONF_FILE" 2>/dev/null && ok "KDE portal routing removed" \
      || fail "KDE portal routing"
  else
    ok "KDE portal routing (not installed)"
  fi
  if command -v systemctl &>/dev/null; then
    for svc in xdg-desktop-portal xdg-desktop-portal-kde xdg-desktop-portal-gtk; do
      systemctl --user restart "$svc" 2>/dev/null || true
    done
  fi
}
