#!/bin/bash
# Rebuild and reinstall the Acrylic Glass KWin effect.
# Safe to run from any session (GNOME, TTY, etc).
set -e

SRC="$(cd "$(dirname "$0")/src/offline/kwin-effects/acrylic-glass" && pwd)"
BUILD="$SRC/build"

PLUGIN_DIR=$(qmake6 -query QT_INSTALL_PLUGINS 2>/dev/null \
  || qtpaths6 --plugin-dir 2>/dev/null \
  || echo "/usr/lib/qt6/plugins")

echo "── Cleaning build dir"
rm -rf "$BUILD"
rm -f "$SRC/src/shaders/onscreen_rounded_core.frag" "$SRC/src/shaders/onscreen_rounded.frag"
mkdir -p "$BUILD"

echo "── Configuring"
cmake -S "$SRC" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release

echo "── Building"
make -C "$BUILD" -j"$(nproc)"

echo "── Installing (needs sudo)"
sudo cp "$BUILD/src/liquidglass.so" "$PLUGIN_DIR/kwin/effects/plugins/liquidglass.so"
sudo cp "$BUILD/src/kcm/kwin_liquidglass_config.so" "$PLUGIN_DIR/kwin/effects/configs/kwin_liquidglass_config.so"

echo "── Done. Log back into KDE Plasma."
