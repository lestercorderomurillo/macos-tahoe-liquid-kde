#!/usr/bin/env bash
# MacTahoe Liquid KDE — test suite
# Nothing escapes.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/src"
STEPS="$SRC/steps"
OFFLINE="$SRC/offline"

PASS=0 FAIL=0 TOTAL=0

assert() {
  local name="$1"; shift
  ((TOTAL++))
  local output
  if output=$("$@" 2>&1); then
    echo -e "  \033[0;32m✓\033[0m  $name"
    ((PASS++))
  else
    echo -e "  \033[0;31m✗\033[0m  $name"
    [[ -n "$output" ]] && echo -e "       \033[0;31m$output\033[0m" | head -5
    ((FAIL++))
  fi
}

# assert file contains a pattern
assert_grep() {
  local name="$1" file="$2" pattern="$3"
  ((TOTAL++))
  if grep -qP "$pattern" "$file" 2>/dev/null; then
    echo -e "  \033[0;32m✓\033[0m  $name"
    ((PASS++))
  else
    echo -e "  \033[0;31m✗\033[0m  $name"
    ((FAIL++))
  fi
}

# assert valid JSON
assert_json() {
  local name="$1" file="$2"
  assert "$name" python3 -c "import json; json.load(open('$file'))"
}

# assert svgz decompresses to valid XML
assert_svgz() {
  local name="$1" file="$2"
  ((TOTAL++))
  if gunzip -c "$file" 2>/dev/null | python3 -c "import sys,xml.etree.ElementTree as ET; ET.parse(sys.stdin)" 2>/dev/null; then
    echo -e "  \033[0;32m✓\033[0m  $name"
    ((PASS++))
  else
    echo -e "  \033[0;31m✗\033[0m  $name"
    ((FAIL++))
  fi
}

echo ""
echo "MacTahoe Liquid KDE — Tests"

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "scripts"
assert "install.sh exists"                  test -f "$REPO/install.sh"
assert "uninstall.sh exists"                test -f "$REPO/uninstall.sh"
assert "install.sh --help exits 0"          bash "$REPO/install.sh" --help
assert "uninstall.sh --help exits 0"        bash "$REPO/uninstall.sh" --help
assert "core.sh exists"                     test -f "$STEPS/core.sh"
assert "functions.sh exists"                test -f "$STEPS/functions.sh"
assert "theme-switch.sh exists"             test -f "$OFFLINE/theme-switch.sh"
assert "set-transparency.sh exists"         test -f "$SRC/scripts/set-transparency.sh"
assert "set-transparency.sh --help exits 0" bash "$SRC/scripts/set-transparency.sh" --help

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "steps (every feature has a step.sh)"
for step in wallpapers fonts cursors icons plasma-theme window-decorations \
            kvantum color-schemes gtk plasmoids menu globalmenu acrylic-glass \
            global-theme layout theme-switch apply; do
  assert "step/$step/step.sh"               test -f "$STEPS/$step/step.sh"
done

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "mirrors"
for mirror in wallpapers fonts icons cursors; do
  assert "mirrors/$mirror.json exists"      test -f "$SRC/mirrors/$mirror.json"
  assert_json "mirrors/$mirror.json valid"  "$SRC/mirrors/$mirror.json"
done

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "plasma theme — dark"
PT_DARK="$OFFLINE/plasma-theme/MacTahoeLiquidKde-Dark"
assert "dark theme dir"                     test -d "$PT_DARK"
assert "dark metadata.json"                 test -f "$PT_DARK/metadata.json"
for svg in dialogs/background widgets/background widgets/translucentbackground \
           widgets/panel-background widgets/tooltip widgets/frame \
           widgets/tasks widgets/button widgets/viewitem widgets/slider \
           widgets/arrows widgets/checkmarks widgets/tabbar; do
  assert_svgz "dark $svg.svgz"              "$PT_DARK/${svg}.svgz"
done

echo ""
echo "plasma theme — light"
PT_LIGHT="$OFFLINE/plasma-theme/MacTahoeLiquidKde-Light"
assert "light theme dir"                    test -d "$PT_LIGHT"
assert "light metadata.json"                test -f "$PT_LIGHT/metadata.json"
for svg in dialogs/background widgets/background widgets/translucentbackground \
           widgets/panel-background widgets/tooltip widgets/frame \
           widgets/tasks widgets/button widgets/viewitem widgets/slider \
           widgets/arrows widgets/checkmarks widgets/tabbar; do
  assert_svgz "light $svg.svgz"             "$PT_LIGHT/${svg}.svgz"
done

echo ""
echo "plasma theme — parity"
# Both variants must have the same set of SVGs
assert "dark/light SVG parity" bash -c "
  dark=\$(find '$PT_DARK' -name '*.svgz' | sed 's|.*/MacTahoeLiquidKde-Dark/||' | sort)
  light=\$(find '$PT_LIGHT' -name '*.svgz' | sed 's|.*/MacTahoeLiquidKde-Light/||' | sort)
  if [[ -z \"\$dark\" ]]; then echo 'ERROR: no dark SVGs found in $PT_DARK'; exit 1; fi
  if [[ -z \"\$light\" ]]; then echo 'ERROR: no light SVGs found in $PT_LIGHT'; exit 1; fi
  diff <(echo \"\$dark\") <(echo \"\$light\")"

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "color schemes"
assert "light .colors file"                 test -f "$OFFLINE/color-schemes/MacTahoeLiquidKdeLight.colors"
assert "dark .colors file"                  test -f "$OFFLINE/color-schemes/MacTahoeLiquidKdeDark.colors"
assert_grep "light has [General]"           "$OFFLINE/color-schemes/MacTahoeLiquidKdeLight.colors" '^\[General\]'
assert_grep "dark has [General]"            "$OFFLINE/color-schemes/MacTahoeLiquidKdeDark.colors" '^\[General\]'

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "kvantum"
KV="$OFFLINE/kvantum/mac-tahoe-liquid-kde"
assert "light kvconfig"                     test -f "$KV/mac-tahoe-liquid-kde.kvconfig"
assert "dark kvconfig"                      test -f "$KV/mac-tahoe-liquid-kdeDark.kvconfig"
assert "light SVG"                          test -f "$KV/mac-tahoe-liquid-kde.svg"
assert "dark SVG"                           test -f "$KV/mac-tahoe-liquid-kdeDark.svg"
# Validate key settings exist in both
for cfg in "$KV/mac-tahoe-liquid-kde.kvconfig" "$KV/mac-tahoe-liquid-kdeDark.kvconfig"; do
  name=$(basename "$cfg")
  assert_grep "$name has reduce_menu_opacity" "$cfg" '^reduce_menu_opacity='
  assert_grep "$name has layout_spacing"      "$cfg" '^layout_spacing='
  assert_grep "$name has blur_translucent"    "$cfg" '^blur_translucent='
  assert_grep "$name has [Menu]"              "$cfg" '^\[Menu\]'
  assert_grep "$name has [MenuItem]"          "$cfg" '^\[MenuItem\]'
  assert_grep "$name has [Window]"            "$cfg" '^\[Window\]'
done
# Light must have frame.left/right (was a bug)
assert_grep "light Window has frame.left"   "$KV/mac-tahoe-liquid-kde.kvconfig" 'frame\.left=10'
assert_grep "light Window has frame.right"  "$KV/mac-tahoe-liquid-kde.kvconfig" 'frame\.right=10'

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "global theme"
for variant in Dark Light; do
  GT="$OFFLINE/look-and-feel/MacTahoeLiquidKde-$variant"
  assert "global theme $variant dir"          test -d "$GT"
  assert_json "global theme $variant json"    "$GT/metadata.json"
  assert "global theme $variant defaults"     test -f "$GT/contents/defaults"
  assert "global theme $variant layout.js"    test -f "$GT/contents/layouts/org.kde.plasma.desktop-layout.js"
  # Defaults must reference correct theme names
  assert_grep "defaults has ColorScheme"      "$GT/contents/defaults" "ColorScheme=MacTahoeLiquidKde$variant"
  assert_grep "defaults has plasmarc theme"   "$GT/contents/defaults" "name=MacTahoeLiquidKde-$variant"
  assert_grep "defaults has aurorae"          "$GT/contents/defaults" "MacTahoeLiquidKde-$variant"
  assert_grep "defaults has cursorTheme"      "$GT/contents/defaults" "cursorTheme="
done

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "aurorae"
for variant in Dark Light; do
  AU="$OFFLINE/aurorae/MacTahoeLiquidKde-$variant"
  assert "aurorae $variant dir"               test -d "$AU"
  assert "aurorae $variant decoration.svg"    test -f "$AU/decoration.svg"
  assert "aurorae ${variant}rc"               test -f "$OFFLINE/aurorae/MacTahoeLiquidKde-${variant}rc"
done

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "gtk"
for variant in Dark Light; do
  GTK="$OFFLINE/gtk/MacTahoeLiquidKde-$variant"
  assert "gtk $variant dir"                   test -d "$GTK"
  assert "gtk3 $variant css"                  test -f "$GTK/gtk-3.0/gtk.css"
  assert "gtk4 $variant css"                  test -f "$GTK/gtk-4.0/gtk.css"
  assert "gtk4 $variant Light.css"            test -f "$GTK/gtk-4.0/gtk-Light.css"
  assert "gtk4 $variant Dark.css"             test -f "$GTK/gtk-4.0/gtk-Dark.css"
  assert "gtk4 $variant assets"              test -d "$GTK/gtk-4.0/assets"
done

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "plasmoids — menu"
MENU="$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.menu"
assert "menu CMakeLists.txt"                test -f "$MENU/CMakeLists.txt"
assert "menu menuapplet.cpp"                test -f "$MENU/menuapplet.cpp"
assert "menu menuapplet.h"                  test -f "$MENU/menuapplet.h"
assert "menu main.xml"                      test -f "$MENU/main.xml"
assert_json "menu metadata.json valid"      "$MENU/metadata.json"
assert "menu qml/main.qml"                  test -f "$MENU/qml/main.qml"
assert "menu qml/AboutWindow.qml"           test -f "$MENU/qml/AboutWindow.qml"
assert "menu qml/config.qml"               test -f "$MENU/qml/config.qml"
assert "menu qml/configGeneral.qml"         test -f "$MENU/qml/configGeneral.qml"
# No old contents/ dir
assert "menu no contents/ (migrated)"       test ! -d "$MENU/contents"
# QML references correct module
assert_grep "menu imports own module"       "$MENU/qml/main.qml" "plasma\.applet\.org\.kde\.mac\.tahoe\.liquid\.menu"
# Has fullRepresentation (required for panel rendering)
assert_grep "menu has fullRepresentation"   "$MENU/qml/main.qml" "fullRepresentation"
# C++ has QMenu
assert_grep "menu uses QMenu"              "$MENU/menuapplet.cpp" "QMenu"
assert_grep "menu has seamless edges"       "$MENU/menuapplet.cpp" "_breeze_menu_seamless_edges"
# Icon config entries
assert_grep "menu config iconAbout"        "$MENU/main.xml" "iconAbout"
assert_grep "menu config iconAppStore"     "$MENU/main.xml" "iconAppStore"
assert_grep "menu config iconLogOut"       "$MENU/main.xml" "iconLogOut"
# C++ reads icon config
assert_grep "menu reads icon config"       "$MENU/menuapplet.cpp" "cfg.readEntry"

echo ""
echo "plasmoids — globalmenu"
GM="$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu"
assert "globalmenu CMakeLists.txt"          test -f "$GM/CMakeLists.txt"
assert "globalmenu appmenuapplet.cpp"       test -f "$GM/appmenuapplet.cpp"
assert "globalmenu appmenuapplet.h"         test -f "$GM/appmenuapplet.h"
assert "globalmenu appmenumodel.cpp"        test -f "$GM/appmenumodel.cpp"
assert "globalmenu appmenumodel.h"          test -f "$GM/appmenumodel.h"
assert_json "globalmenu metadata.json"      "$GM/metadata.json"
assert "globalmenu qml/main.qml"            test -f "$GM/qml/main.qml"
assert "globalmenu qml/MenuDelegate.qml"    test -f "$GM/qml/MenuDelegate.qml"
# App name label exists
assert_grep "globalmenu has appNameLabel"   "$GM/qml/main.qml" "appNameLabel"
assert_grep "globalmenu has activeAppName"  "$GM/appmenumodel.h" "activeAppName"
# MenuDelegate has font weight
assert_grep "delegate has font.weight"      "$GM/qml/MenuDelegate.qml" "font\.weight"

echo ""
echo "plasmoids — launcher"
LAUNCHER="$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.launcher"
assert_json "launcher metadata.json"        "$LAUNCHER/metadata.json"
assert "launcher has QML main"              test -f "$LAUNCHER/contents/ui/main.qml"

echo ""
echo "plasmoids — trashcan"
TRASH="$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.trashcan"
assert_json "trashcan metadata.json"        "$TRASH/metadata.json"
assert "trashcan has QML main"              test -f "$TRASH/contents/ui/main.qml"

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "acrylic glass"
AG="$OFFLINE/kwin-effects/acrylic-glass"
assert "acrylic CMakeLists.txt"             test -f "$AG/CMakeLists.txt"
assert "acrylic blur.cpp"                   test -f "$AG/src/blur.cpp"
assert "acrylic blur.h"                     test -f "$AG/src/blur.h"
assert "acrylic blur.kcfg"                  test -f "$AG/src/blur.kcfg"
# kcfg must have all keys referenced by C++
for key in BlurStrength NoiseStrength BlurDecorations WindowCornerRadius \
           DockCornerRadius PopupCornerRadius HighlightStrength HighlightWidth \
           MagnifyGlassStrength RefractionWidth RgbDriftStrength; do
  assert_grep "kcfg has $key"              "$AG/src/blur.kcfg" "name=\"$key\""
done
# Shaders exist
# onscreen_rounded*.frag are generated/gitignored — check texture shaders instead
assert "texture_core.frag"                  test -f "$AG/src/shaders/texture_core.frag"
assert "upsample_core.frag"                 test -f "$AG/src/shaders/upsample_core.frag"
assert "downsample_core.frag"               test -f "$AG/src/shaders/downsample_core.frag"
assert "noise_core.frag"                    test -f "$AG/src/shaders/noise_core.frag"

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "layout"
assert "layout mac-tahoe.js"                test -f "$OFFLINE/layouts/mac-tahoe.js"
assert "layout default.js"                  test -f "$OFFLINE/layouts/default.js"
# Layout must reference correct plasmoid IDs (dot-based for C++ applets)
assert_grep "layout uses menu ID"           "$OFFLINE/layouts/mac-tahoe.js" "org\.kde\.mac\.tahoe\.liquid\.menu"
assert_grep "layout uses globalmenu ID"     "$OFFLINE/layouts/mac-tahoe.js" "org\.kde\.mac\.tahoe\.liquid\.globalmenu"
assert_grep "layout uses launcher ID"       "$OFFLINE/layouts/mac-tahoe.js" "org\.kde\.mac-tahoe-liquid-kde\.launcher"
assert_grep "layout uses trashcan ID"       "$OFFLINE/layouts/mac-tahoe.js" "org\.kde\.mac-tahoe-liquid-kde\.trashcan"
assert_grep "layout uses panelspacer"       "$OFFLINE/layouts/mac-tahoe.js" "org\.kde\.plasma\.panelspacer"
assert_grep "layout uses systemtray"        "$OFFLINE/layouts/mac-tahoe.js" "org\.kde\.plasma\.systemtray"
assert_grep "layout uses digitalclock"      "$OFFLINE/layouts/mac-tahoe.js" "org\.kde\.plasma\.digitalclock"
assert_grep "layout uses icontasks"         "$OFFLINE/layouts/mac-tahoe.js" "org\.kde\.plasma\.icontasks"
assert_grep "layout uses colorizer"         "$OFFLINE/layouts/mac-tahoe.js" "luisbocanegra\.panel\.colorizer"

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "install step config (acrylic glass preset)"
AG_STEP="$STEPS/acrylic-glass/step.sh"
for key in BlurStrength HighlightStrength HighlightWidth DockCornerRadius \
           WindowCornerRadius PopupCornerRadius RimStrength ShadowStrength; do
  assert_grep "step sets $key"             "$AG_STEP" "$key"
done

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "naming conventions"
# No references to old names (Kpple, kpple) in source files
assert "no 'Kpple' in plasmoid sources" bash -c "
  ! grep -rli 'kpple' '$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.menu/' \
    '$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu/' \
    --include='*.qml' --include='*.cpp' --include='*.h' --include='*.json' 2>/dev/null"
# No 'Kmenu' in commits-facing code
assert "no 'Kmenu' in menu sources" bash -c "
  ! grep -rli 'kmenu' '$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.menu/' \
    --include='*.qml' --include='*.cpp' --include='*.h' --include='*.json' 2>/dev/null"
# Metadata IDs follow convention
assert_grep "menu ID uses dots"            "$MENU/metadata.json" '"Id": "org\.kde\.mac\.tahoe\.liquid\.menu"'
assert_grep "globalmenu ID uses dots"      "$GM/metadata.json" '"Id": "org\.kde\.mac\.tahoe\.liquid\.globalmenu"'
assert_grep "launcher ID uses kebab"       "$LAUNCHER/metadata.json" '"Id": "org\.kde\.mac-tahoe-liquid-kde\.launcher"'
assert_grep "trashcan ID uses kebab"       "$TRASH/metadata.json" '"Id": "org\.kde\.mac-tahoe-liquid-kde\.trashcan"'

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "transparency script coverage"
TS="$SRC/scripts/set-transparency.sh"
assert_grep "updates kvantum menu opacity"  "$TS" "reduce_menu_opacity"
assert_grep "updates kvantum color alpha"   "$TS" "window\\\\\.color"
assert_grep "updates plasma SVGs"           "$TS" "svgz"
assert_grep "updates gtk4 color-mix"        "$TS" "window_bg_color"
assert_grep "updates gtk3 background.csd"   "$TS" "background\.csd"
assert_grep "has --dock parameter"          "$TS" "\-\-dock"
assert_grep "has --apply parameter"         "$TS" "\-\-apply"

# ═══════════════════════════════════════════════════════════════════
if command -v cmake &>/dev/null; then
  echo ""
  echo "builds"
  for applet in "$MENU" "$GM"; do
    name=$(basename "$applet")
    tmpbuild=$(mktemp -d)
    assert "$name configures" cmake -S "$applet" -B "$tmpbuild" -DCMAKE_BUILD_TYPE=Release
    assert "$name builds"     cmake --build "$tmpbuild"
    # Check .so was produced
    assert "$name produces .so" bash -c "find '$tmpbuild' -name '*.so' | grep -q ."
    rm -rf "$tmpbuild"
  done
fi

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ $FAIL -eq 0 ]]; then
  echo -e "  \033[0;32m$PASS/$TOTAL passed\033[0m"
else
  echo -e "  \033[0;31m$FAIL/$TOTAL failed\033[0m"
fi
echo ""

exit $FAIL
