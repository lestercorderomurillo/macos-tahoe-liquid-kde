#!/usr/bin/env bash
# MacTahoe Liquid KDE — global theme (look-and-feel) step

SRC_DIR="$OFFLINE/look-and-feel"
DEST_DIR="$HOME/.local/share/plasma/look-and-feel"

install() {
  mkdir -p "$DEST_DIR"
  for theme in "$SRC_DIR"/MacTahoeLiquidKde-*/; do
    [[ -d "$theme" ]] || continue
    local name
    name=$(basename "$theme")
    local id
    id=$(sed -n 's/.*"Id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$theme/metadata.json" 2>/dev/null)
    [[ -n "$id" ]] || continue
    safe_copy "$theme" "$DEST_DIR/$id"
    ok "$name"
  done
}

uninstall() {
  for theme in "$DEST_DIR"/org.kde.mac-tahoe-liquid-kde.*; do
    [[ -d "$theme" ]] || continue
    rm -rf "$theme" 2>/dev/null && ok "$(basename "$theme")"
  done
}
