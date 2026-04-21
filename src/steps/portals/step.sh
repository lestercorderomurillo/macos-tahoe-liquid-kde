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
  # Routing rules:
  #   * Settings → gtk
  #     libadwaita queries Settings for gtk-decoration-layout /
  #     gtk-theme / color-scheme. portal-kde answers with KDE's own
  #     schema (Aurorae "XIA" button layout), which libadwaita can't
  #     parse → falls back to right-side close-only controls and
  #     drops the mac traffic lights. portal-gtk reads gsettings and
  #     returns the `close,minimize,maximize:` format libadwaita
  #     expects, putting buttons on the left as configured.
  #   * FileChooser / AppChooser → kde
  #     "Open with…" and file pickers render as native Qt/KDE
  #     dialogs instead of the stale GTK/Nautilus ones.
  #   * No `default=…` — let other portals (Notification, Location,
  #     etc.) use their compiled-in fallback.
  cat > "$CONF_FILE" <<'EOF'
[preferred]
org.freedesktop.impl.portal.Settings=gtk
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
