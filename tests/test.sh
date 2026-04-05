#!/usr/bin/env bash
# MacTahoe Liquid KDE — test suite
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/src"
STEPS="$SRC/steps"
OFFLINE="$SRC/offline"

PASS=0 FAIL=0 TOTAL=0

assert() {
  local name="$1"; shift
  ((TOTAL++))
  if "$@" &>/dev/null; then
    echo -e "  \033[0;32m✓\033[0m  $name"
    ((PASS++))
  else
    echo -e "  \033[0;31m✗\033[0m  $name"
    ((FAIL++))
  fi
}

echo ""
echo "MacTahoe Liquid KDE — Tests"
echo ""

# ── install.sh ──────────────────────────────────────────────────
echo "install.sh"
assert "exists and is executable"           test -f "$REPO/install.sh"
assert "--help exits 0"                     bash "$REPO/install.sh" --help

# ── uninstall.sh ────────────────────────────────────────────────
echo ""
echo "uninstall.sh"
assert "exists and is executable"           test -f "$REPO/uninstall.sh"
assert "--help exits 0"                     bash "$REPO/uninstall.sh" --help

# ── steps ───────────────────────────────────────────────────────
echo ""
echo "steps"
for step in wallpapers fonts cursors icons plasma-theme window-decorations \
            kvantum color-schemes gtk plasmoids menu globalmenu acrylic-glass \
            global-theme layout theme-switch apply; do
  assert "step $step exists"                test -f "$STEPS/$step/step.sh"
done

# ── offline assets ──────────────────────────────────────────────
echo ""
echo "offline assets"
assert "plasma theme Dark"                  test -d "$OFFLINE/plasma-theme/MacTahoeLiquidKde-Dark"
assert "plasma theme Light"                 test -d "$OFFLINE/plasma-theme/MacTahoeLiquidKde-Light"
assert "color scheme Dark"                  test -f "$OFFLINE/color-schemes/MacTahoeLiquidKdeDark.colors"
assert "color scheme Light"                 test -f "$OFFLINE/color-schemes/MacTahoeLiquidKdeLight.colors"
assert "kvantum config"                     test -f "$OFFLINE/kvantum/mac-tahoe-liquid-kde/mac-tahoe-liquid-kde.kvconfig"
assert "kvantum dark config"                test -f "$OFFLINE/kvantum/mac-tahoe-liquid-kde/mac-tahoe-liquid-kdeDark.kvconfig"
assert "global theme Dark"                  test -f "$OFFLINE/look-and-feel/MacTahoeLiquidKde-Dark/metadata.json"
assert "global theme Light"                 test -f "$OFFLINE/look-and-feel/MacTahoeLiquidKde-Light/metadata.json"
assert "global theme Dark has layout"       test -f "$OFFLINE/look-and-feel/MacTahoeLiquidKde-Dark/contents/layouts/org.kde.plasma.desktop-layout.js"
assert "global theme Light has layout"      test -f "$OFFLINE/look-and-feel/MacTahoeLiquidKde-Light/contents/layouts/org.kde.plasma.desktop-layout.js"
assert "layout script"                      test -f "$OFFLINE/layouts/mac-tahoe.js"

# ── plasmoids ───────────────────────────────────────────────────
echo ""
echo "plasmoids"
assert "menu CMakeLists.txt"                test -f "$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.menu/CMakeLists.txt"
assert "menu metadata.json"                 test -f "$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.menu/metadata.json"
assert "menu C++ source"                    test -f "$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.menu/menuapplet.cpp"
assert "menu QML main"                      test -f "$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.menu/qml/main.qml"
assert "globalmenu CMakeLists.txt"          test -f "$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu/CMakeLists.txt"
assert "globalmenu C++ source"              test -f "$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu/appmenuapplet.cpp"
assert "launcher metadata.json"            test -f "$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.launcher/metadata.json"
assert "trashcan metadata.json"            test -f "$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.trashcan/metadata.json"

# ── metadata validation ─────────────────────────────────────────
echo ""
echo "metadata"
assert "menu metadata valid JSON"           python3 -c "import json; json.load(open('$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.menu/metadata.json'))"
assert "globalmenu metadata valid JSON"     python3 -c "import json; json.load(open('$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu/metadata.json'))"
assert "global theme Dark valid JSON"       python3 -c "import json; json.load(open('$OFFLINE/look-and-feel/MacTahoeLiquidKde-Dark/metadata.json'))"
assert "global theme Light valid JSON"      python3 -c "import json; json.load(open('$OFFLINE/look-and-feel/MacTahoeLiquidKde-Light/metadata.json'))"

# ── summary ─────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ $FAIL -eq 0 ]]; then
  echo -e "  \033[0;32m$PASS/$TOTAL passed\033[0m"
else
  echo -e "  \033[0;31m$FAIL/$TOTAL failed\033[0m"
fi
echo ""

exit $FAIL
