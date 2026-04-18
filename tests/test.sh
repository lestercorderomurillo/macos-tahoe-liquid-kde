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

assert_color_key_parity() {
  local name="$1" light_file="$2" dark_file="$3"
  ((TOTAL++))
  local output
  if output=$(python3 - "$light_file" "$dark_file" <<'PY'
import sys
from pathlib import Path

def parse(path):
    sections = {}
    sec = None
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            sec = line[1:-1]
            sections.setdefault(sec, {})
            continue
        if "=" in line and sec is not None:
            key, value = line.split("=", 1)
            sections[sec][key.strip()] = value.strip()
    return sections

light = parse(sys.argv[1])
dark = parse(sys.argv[2])
errors = []
for sec in sorted(set(light) | set(dark)):
    lkeys = set(light.get(sec, {}))
    dkeys = set(dark.get(sec, {}))
    if lkeys != dkeys:
        errors.append(f"[{sec}]")
        if lkeys - dkeys:
            errors.append("  light-only: " + ", ".join(sorted(lkeys - dkeys)))
        if dkeys - lkeys:
            errors.append("  dark-only: " + ", ".join(sorted(dkeys - lkeys)))

if errors:
    print("\n".join(errors))
    raise SystemExit(1)
PY
  ); then
    echo -e "  \033[0;32m✓\033[0m  $name"
    ((PASS++))
  else
    echo -e "  \033[0;31m✗\033[0m  $name"
    [[ -n "$output" ]] && echo -e "       \033[0;31m$output\033[0m" | head -5
    ((FAIL++))
  fi
}

echo ""
echo "MacTahoe Liquid KDE — Tests"

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "scripts"
assert "VERSION file exists"                 test -f "$REPO/VERSION"
assert_grep "VERSION is semver"             "$REPO/VERSION" '^[0-9]+\.[0-9]+\.[0-9]+$'
assert "install.sh exists"                  test -f "$REPO/install.sh"
assert "uninstall.sh exists"                test -f "$REPO/uninstall.sh"
assert "install.sh --help exits 0"          bash "$REPO/install.sh" --help
assert "uninstall.sh --help exits 0"        bash "$REPO/uninstall.sh" --help
assert "core.sh exists"                     test -f "$STEPS/core.sh"
assert "functions.sh exists"                test -f "$STEPS/functions.sh"
assert_grep "core.sh has CLI banner"        "$STEPS/core.sh" '_show_banner\(\)'
assert_grep "core.sh banner prints version" "$STEPS/core.sh" 'MacTahoe Liquid KDE .*THEME_VERSION'
assert "theme-switch.sh exists"             test -f "$OFFLINE/theme-switch.sh"
assert "set-transparency.sh exists"         test -f "$SRC/scripts/set-transparency.sh"
assert "set-transparency.sh --help exits 0" bash "$SRC/scripts/set-transparency.sh" --help

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "steps (every feature has a step.sh)"
for step in wallpapers fonts cursors icons plasma-theme window-decorations \
            kvantum color-schemes gtk plasmoids globalmenu acrylic-glass \
            global-theme layout theme-switch apply nautilus; do
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
assert_color_key_parity "light/dark .colors key parity" \
  "$OFFLINE/color-schemes/MacTahoeLiquidKdeLight.colors" \
  "$OFFLINE/color-schemes/MacTahoeLiquidKdeDark.colors"

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
echo "plasmoids — old menu removed"
assert "no old menu plasmoid dir"    test ! -d "$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.menu"
assert "no old menu step dir"        test ! -d "$STEPS/menu"

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
assert "globalmenu qml/AboutWindow.qml"     test -f "$GM/qml/AboutWindow.qml"
assert "globalmenu qml/configSystemMenu"    test -f "$GM/qml/configSystemMenu.qml"
# App name button exists
assert_grep "globalmenu has appNameButton"  "$GM/qml/main.qml" "appNameButton"
assert_grep "globalmenu has activeAppName"  "$GM/appmenumodel.h" "activeAppName"
# System menu button exists
assert_grep "globalmenu has systemMenuBtn"  "$GM/qml/main.qml" "systemMenuButton"
# C++ has system menu
assert_grep "globalmenu triggerSystemMenu"  "$GM/appmenuapplet.cpp" "triggerSystemMenu"
assert_grep "globalmenu aboutRequested"     "$GM/appmenuapplet.h" "aboutRequested"
assert_grep "globalmenu has seamless edges" "$GM/appmenuapplet.cpp" "_breeze_menu_seamless_edges"
assert_grep "globalmenu reads icon config"  "$GM/appmenuapplet.cpp" "cfg.readEntry"
# Window menu
assert_grep "globalmenu triggerWindowMenu"  "$GM/appmenuapplet.cpp" "triggerWindowMenu"
# Icon config entries in merged config
assert_grep "globalmenu config iconAbout"   "$GM/main.xml" "iconAbout"
assert_grep "globalmenu config iconAppStore" "$GM/main.xml" "iconAppStore"
assert_grep "globalmenu config iconLogOut"  "$GM/main.xml" "iconLogOut"
assert_grep "globalmenu config menuIcon"    "$GM/main.xml" "menuIcon"
assert_grep "globalmenu config cmdSleep"    "$GM/main.xml" "cmdSleep"
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
assert "acrylic blur_config.ui"             test -f "$AG/src/kcm/blur_config.ui"
# kcfg must have all keys referenced by C++
for key in BlurStrength NoiseStrength BlurDecorations WindowCornerRadius \
           DockCornerRadius PopupCornerRadius HighlightStrength HighlightWidth \
           MagnifyGlassStrength RefractionWidth RgbDriftStrength; do
  assert_grep "kcfg has $key"              "$AG/src/blur.kcfg" "name=\"$key\""
done
# KCM layout should be tab-based and expose core options.
assert_grep "kcm has tab widget"            "$AG/src/kcm/blur_config.ui" "QTabWidget"
assert_grep "kcm has Glass tab"             "$AG/src/kcm/blur_config.ui" "<string>Glass</string>"
assert_grep "kcm has Corners tab"           "$AG/src/kcm/blur_config.ui" "<string>Corners</string>"
assert_grep "kcm has Window Rules tab"      "$AG/src/kcm/blur_config.ui" "<string>Window Rules</string>"
assert_grep "kcm exposes BlurDecorations"   "$AG/src/kcm/blur_config.ui" "name=\"kcfg_BlurDecorations\""
assert_grep "kcm exposes NoiseStrength"     "$AG/src/kcm/blur_config.ui" "name=\"kcfg_NoiseStrength\""
# Shaders exist
# onscreen_rounded*.frag are generated/gitignored — check texture shaders instead
assert "texture_core.frag"                  test -f "$AG/src/shaders/texture_core.frag"
assert "upsample_core.frag"                 test -f "$AG/src/shaders/upsample_core.frag"
assert "downsample_core.frag"               test -f "$AG/src/shaders/downsample_core.frag"
assert "noise_core.frag"                    test -f "$AG/src/shaders/noise_core.frag"
assert "sdf.glsl"                           test -f "$AG/src/shaders/sdf.glsl"
assert "blur.glsl"                          test -f "$AG/src/shaders/blur.glsl"
assert "distort.glsl"                       test -f "$AG/src/shaders/distort.glsl"
assert "highlight.glsl"                     test -f "$AG/src/shaders/highlight.glsl"
assert_grep "onscreen shader includes sdf"  "$AG/src/shaders/onscreen_rounded.glsl" "#include \"sdf\\.glsl\""
assert_grep "onscreen shader includes blur" "$AG/src/shaders/onscreen_rounded.glsl" "#include \"blur\\.glsl\""
assert_grep "onscreen shader includes distort" "$AG/src/shaders/onscreen_rounded.glsl" "#include \"distort\\.glsl\""
assert_grep "onscreen shader includes highlight" "$AG/src/shaders/onscreen_rounded.glsl" "#include \"highlight\\.glsl\""
assert_grep "cmake preprocesses shader includes" "$AG/src/CMakeLists.txt" "preprocess_shader_includes"
assert_grep "cmake include list has sdf"    "$AG/src/CMakeLists.txt" "sdf\\.glsl"
assert_grep "cmake include list has blur"   "$AG/src/CMakeLists.txt" "blur\\.glsl"
assert_grep "cmake include list has distort" "$AG/src/CMakeLists.txt" "distort\\.glsl"
assert_grep "cmake include list has highlight" "$AG/src/CMakeLists.txt" "highlight\\.glsl"
assert_grep "blur scaling checks either axis" "$AG/src/blur.cpp" "xScale\\(\\), 1\\.0\\) \\|\\| !qFuzzyCompare\\(data\\.yScale\\(\\), 1\\.0\\)"

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "layout"
assert "layout mac-tahoe.js"                test -f "$OFFLINE/layouts/mac-tahoe.js"
assert "layout default.js"                  test -f "$OFFLINE/layouts/default.js"
# Layout must reference correct plasmoid IDs (dot-based for C++ applets)
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
echo "installer steps"
GM_STEP="$STEPS/globalmenu/step.sh"
# globalmenu step cleans up old standalone menu on install and uninstall
assert_grep "gm step removes old menu so"  "$GM_STEP" "org\.kde\.mac\.tahoe\.liquid\.menu\.so"
assert_grep "gm step removes old qml menu" "$GM_STEP" "org\.kde\.mac-tahoe-liquid-kde\.menu"
# cleans up pre-rename plugins (from before "liquid" was added to the ID)
assert_grep "gm step removes pre-rename"   "$GM_STEP" "org\.kde\.mac\.tahoe\.globalmenu\.so"
# layout only adds globalmenu (not standalone menu)
assert "layout no standalone menu widget" bash -c "! grep -q 'org\.kde\.mac\.tahoe\.liquid\.menu' '$OFFLINE/layouts/mac-tahoe.js'"
# core.sh feature list no longer has standalone menu
assert "core.sh no menu feature"     bash -c "! grep -qE '_FEATURES=.*\bmenu\b[^g]' '$STEPS/core.sh'"

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "naming conventions"
# No references to old names (Kpple, kpple) in globalmenu sources
assert "no 'Kpple' in plasmoid sources" bash -c "
  ! grep -rli 'kpple' '$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu/' \
    --include='*.qml' --include='*.cpp' --include='*.h' --include='*.json' 2>/dev/null"
# No 'Kmenu' in globalmenu sources
assert "no 'Kmenu' in globalmenu sources" bash -c "
  ! grep -rli 'kmenu' '$OFFLINE/plasmoids/org.kde.mac-tahoe-liquid-kde.globalmenu/' \
    --include='*.qml' --include='*.cpp' --include='*.h' --include='*.json' 2>/dev/null"
# Metadata IDs follow convention
assert_grep "globalmenu ID uses dots"      "$GM/metadata.json" '"Id": "org\.kde\.mac\.tahoe\.liquid\.globalmenu"'
assert_grep "launcher ID uses kebab"       "$LAUNCHER/metadata.json" '"Id": "org\.kde\.mac-tahoe-liquid-kde\.launcher"'
assert_grep "trashcan ID uses kebab"       "$TRASH/metadata.json" '"Id": "org\.kde\.mac-tahoe-liquid-kde\.trashcan"'

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "nautilus step"
N_STEP="$STEPS/nautilus/step.sh"
assert "nautilus step exists"              test -f "$N_STEP"
assert "nautilus offline dir exists"       test -d "$OFFLINE/nautilus"
# deps() declares nautilus package
assert_grep "nautilus step declares dep"   "$N_STEP" "^[[:space:]]*echo \"nautilus\""
# KDE check
assert_grep "nautilus step checks KDE"     "$N_STEP" "XDG_CURRENT_DESKTOP"
# xdg-mime calls — the Nautilus .desktop used as default; Dolphin used in uninstall
assert_grep "nautilus step refs Nautilus desktop" "$N_STEP" "org\.gnome\.Nautilus\.desktop"
assert_grep "nautilus step refs Dolphin desktop"  "$N_STEP" "org\.kde\.dolphin\.desktop"
assert_grep "nautilus step uses xdg-mime"         "$N_STEP" "xdg-mime default"
# feature list includes nautilus
assert_grep "core.sh has nautilus feature" "$STEPS/core.sh" "_FEATURES=.*\bnautilus\b"
assert_grep "core.sh _ALL has nautilus"    "$STEPS/core.sh" "_ALL_FEATURES=.*\bnautilus\b"
# features.json has nautilus
assert_grep "features.json has nautilus"   "$REPO/features.json" '"nautilus"'
# install.sh help mentions --nautilus
assert_grep "install.sh doc --nautilus"    "$REPO/install.sh" "\-\-nautilus"

# ═══════════════════════════════════════════════════════════════════
echo ""
echo "transparency script coverage"
TS="$SRC/scripts/set-transparency.sh"
assert_grep "updates kvantum menu opacity"  "$TS" "reduce_menu_opacity"
assert_grep "updates kvantum color alpha"   "$TS" "window\\\\\.color"
assert_grep "updates plasma SVGs"           "$TS" "svgz"
assert_grep "updates gtk4 color-mix"        "$TS" "window_bg_color"
assert_grep "updates gtk3 background.csd"   "$TS" "background\.csd"

# theme-switch has direct color scheme fallback (plasma-apply-colorscheme is unreliable)
TSW="$OFFLINE/theme-switch.sh"
assert_grep "theme-switch has direct color fallback" "$TSW" "_apply_color_groups_direct"
assert_grep "theme-switch reads .colors file"        "$TSW" "\.colors"
assert_grep "theme-switch auto uses detect_mode"      "$TSW" 'apply "\$\(detect_mode\)"'
assert_grep "theme-switch syncs WM colors"            "$TSW" 'Colors:\*|ColorEffects:\*|WM'
assert_grep "has --dock parameter"          "$TS" "\-\-dock"
assert_grep "has --apply parameter"         "$TS" "\-\-apply"
assert_grep "dock default constant is 12"   "$TS" '^DEFAULT_DOCK_PCT=12$'
assert_grep "dock help text says default 12" "$TS" 'default: 12'
assert_grep "reinstall icon is green"       "$STEPS/functions.sh" '^reinstall\(\).*GREEN'

# ═══════════════════════════════════════════════════════════════════
if command -v cmake &>/dev/null; then
  echo ""
  echo "builds"
  for applet in "$GM"; do
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
# integration tests (sandboxed HOME — safe to run anywhere)
if [[ -f "$(dirname "${BASH_SOURCE[0]}")/test-integration.sh" ]]; then
  # shellcheck disable=SC1090
  source "$(dirname "${BASH_SOURCE[0]}")/test-integration.sh"
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
