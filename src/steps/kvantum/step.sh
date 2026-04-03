#!/usr/bin/env bash
# MacTahoe Liquid KDE — kvantum theme step

SRC_DIR="$OFFLINE/kvantum/mac-tahoe-liquid-kde"
DEST_DIR="$HOME/.config/Kvantum/mac-tahoe-liquid-kde"

deps() {
  echo "kvantummanager:kvantum"
}

install() {
  if [[ ! -d "$SRC_DIR" ]]; then
    fail "Kvantum theme source not found at $SRC_DIR"
    return 1
  fi

  local existed=false
  [[ -d "$DEST_DIR" ]] && ls "$DEST_DIR"/*.kvconfig &>/dev/null 2>&1 && existed=true

  mkdir -p "$DEST_DIR"
  cp -f "$SRC_DIR"/*.kvconfig "$DEST_DIR/" 2>/dev/null
  cp -f "$SRC_DIR"/*.svg      "$DEST_DIR/" 2>/dev/null

  if [[ -d "$DEST_DIR" ]] && ls "$DEST_DIR"/*.kvconfig &>/dev/null 2>&1; then
    $existed && reinstall "mac-tahoe-liquid-kde theme" || ok "mac-tahoe-liquid-kde theme (installed)"
  else
    fail "mac-tahoe-liquid-kde theme (copy failed)"
  fi

  if command -v kwriteconfig6 &>/dev/null; then
    kwriteconfig6 --file kdeglobals --group KDE --key widgetStyle kvantum
    ok "Widget style installed"
  fi
}

uninstall() {
  if [[ -d "$DEST_DIR" ]]; then
    if command -v kwriteconfig6 &>/dev/null; then
      kwriteconfig6 --file kdeglobals --group KDE --key widgetStyle Breeze
      ok "Widget style reset to Breeze"
    fi
    if command -v kvantummanager &>/dev/null; then
      QT_QPA_PLATFORM=offscreen kvantummanager --set Default &>/dev/null || true
    fi
    rm -rf "$DEST_DIR" 2>/dev/null && ok "MacTahoeLiquidKde theme removed" || fail "MacTahoeLiquidKde theme"
  else
    ok "MacTahoeLiquidKde theme (not installed)"
  fi
}
