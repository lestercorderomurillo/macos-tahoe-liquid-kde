#!/usr/bin/env bash
# MacTahoe Liquid KDE — global menu C++ applet step

SRC_DIR="$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu"
BUILD_DIR="$SRC_DIR/build"
DEST_SO="/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so"

deps() {
  echo "cmake"
  echo "g++:gcc"
  echo "pkg-config:pkgconf"
}

build() {
  [[ -f "$SRC_DIR/CMakeLists.txt" ]] || { warn "Global Menu source not found — skipping"; return 0; }

  rm -rf "$BUILD_DIR"
  mkdir -p "$BUILD_DIR"

  if cmake -S "$SRC_DIR" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release &>/dev/null; then
    if make -C "$BUILD_DIR" -j"$(nproc)" &>/dev/null; then
      ok "Global Menu built"
    else
      fail "Global Menu: build failed"
    fi
  else
    fail "Global Menu: cmake configure failed"
  fi
}

install() {
  local so="$BUILD_DIR/bin/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so"
  [[ -f "$so" ]] || return 0

  if sudo cp "$so" "${DEST_SO}.tmp" && sudo mv -f "${DEST_SO}.tmp" "$DEST_SO"; then
    ok "Global Menu installed"
  else
    fail "Global Menu: could not install .so (sudo required)"
  fi
}

uninstall() {
  [[ -f "$DEST_SO" ]] && sudo rm -f "$DEST_SO" 2>/dev/null && ok "Global Menu .so removed"
}
