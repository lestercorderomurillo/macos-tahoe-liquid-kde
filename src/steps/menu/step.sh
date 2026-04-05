#!/usr/bin/env bash
# MacTahoe Liquid KDE — Menu C++ applet step

SRC_DIR="$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.menu"
BUILD_DIR="$SRC_DIR/build"
DEST_SO="/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.menu.so"

deps() {
  echo "cmake"
  echo "g++:gcc"
  echo "pkg-config:pkgconf"
}

build() {
  [[ -f "$SRC_DIR/CMakeLists.txt" ]] || { warn "Menu source not found — skipping"; return 0; }

  rm -rf "$BUILD_DIR"
  mkdir -p "$BUILD_DIR"

  if cmake -S "$SRC_DIR" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release &>/dev/null; then
    if make -C "$BUILD_DIR" -j"$(nproc)" &>/dev/null; then
      ok "Menu built"
    else
      fail "Menu: build failed"
    fi
  else
    fail "Menu: cmake configure failed"
  fi
}

install() {
  # remove old pure-QML menu plasmoid (superseded by C++ build)
  local old_qml="$HOME/.local/share/plasma/plasmoids/org.kde.mac-tahoe-liquid-kde.menu"
  [[ -d "$old_qml" ]] && rm -rf "$old_qml" && ok "Removed old QML menu"

  local so="$BUILD_DIR/bin/plasma/applets/org.kde.mac.tahoe.liquid.menu.so"
  [[ -f "$so" ]] || return 0

  if sudo cp "$so" "${DEST_SO}.tmp" && sudo mv -f "${DEST_SO}.tmp" "$DEST_SO"; then
    ok "Menu installed"
  else
    fail "Menu: could not install .so (sudo required)"
  fi
}

uninstall() {
  [[ -f "$DEST_SO" ]] && sudo rm -f "$DEST_SO" 2>/dev/null && ok "Menu .so removed"
  local old_qml="$HOME/.local/share/plasma/plasmoids/org.kde.mac-tahoe-liquid-kde.menu"
  [[ -d "$old_qml" ]] && rm -rf "$old_qml" && ok "Removed old QML menu"
}
