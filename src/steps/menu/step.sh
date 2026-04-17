#!/usr/bin/env bash
# MacTahoe Liquid KDE — Menu cleanup step
# The standalone Menu plasmoid has been merged into the Global Menu.
# This step only removes old installations.

DEST_SO="/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.menu.so"

install() {
  [[ -f "$DEST_SO" ]] && sudo rm -f "$DEST_SO" 2>/dev/null && ok "Removed old standalone Menu .so"
  local old_qml="$HOME/.local/share/plasma/plasmoids/org.kde.mac-tahoe-liquid-kde.menu"
  [[ -d "$old_qml" ]] && rm -rf "$old_qml" && ok "Removed old QML menu"
}

uninstall() {
  [[ -f "$DEST_SO" ]] && sudo rm -f "$DEST_SO" 2>/dev/null && ok "Menu .so removed"
  local old_qml="$HOME/.local/share/plasma/plasmoids/org.kde.mac-tahoe-liquid-kde.menu"
  [[ -d "$old_qml" ]] && rm -rf "$old_qml" && ok "Removed old QML menu"
}
