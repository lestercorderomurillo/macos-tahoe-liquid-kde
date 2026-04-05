#!/usr/bin/env bash
# MacTahoe Liquid KDE — acrylic glass KWin effect step
# absorbs logic from the old src/scripts/rebuild-kwin-effects.sh

SRC_DIR="$OFFLINE/kwin-effects/acrylic-glass"
BUILD_DIR="$SRC_DIR/build"

deps() {
  echo "cmake"
  echo "g++:gcc"
  echo "pkg-config:pkgconf"
}

build() {
  [[ -f "$SRC_DIR/CMakeLists.txt" ]] || return 0

  rm -rf "$BUILD_DIR"
  rm -f "$SRC_DIR/src/shaders/onscreen_rounded_core.frag" "$SRC_DIR/src/shaders/onscreen_rounded.frag"
  mkdir -p "$BUILD_DIR"

  # disable conflicting effects before build
  kwriteconfig6 --file kwinrc --group Plugins --key glassEnabled false 2>/dev/null || true
  kwriteconfig6 --file kwinrc --group Plugins --key blurEnabled false 2>/dev/null || true
  local q
  q=$(qdbus_cmd) && {
    "$q" org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect glass &>/dev/null || true
    "$q" org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect blur &>/dev/null || true
  }

  if cmake -S "$SRC_DIR" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release &>/dev/null; then
    if make -C "$BUILD_DIR" -j"$(nproc)" &>/dev/null; then
      ok "Acrylic Glass built"
    else
      fail "Acrylic Glass build failed"
    fi
  else
    fail "Acrylic Glass cmake failed"
  fi
}

install() {
  local plugin_dir effect_so config_so dest_effect dest_config
  plugin_dir=$(qmake6 -query QT_INSTALL_PLUGINS 2>/dev/null \
    || qtpaths6 --plugin-dir 2>/dev/null \
    || pkg-config --variable=plugindir Qt6Core 2>/dev/null \
    || echo "/usr/lib/qt6/plugins")
  effect_so="$BUILD_DIR/src/liquidglass.so"
  config_so="$BUILD_DIR/src/kcm/kwin_liquidglass_config.so"
  dest_effect="$plugin_dir/kwin/effects/plugins/liquidglass.so"
  dest_config="$plugin_dir/kwin/effects/configs/kwin_liquidglass_config.so"

  [[ -f "$effect_so" ]] || return 0

  # unload before replacing .so to avoid crash
  local q
  q=$(qdbus_cmd) && {
    kwriteconfig6 --file kwinrc --group Plugins --key liquidglassEnabled false 2>/dev/null || true
    "$q" org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect liquidglass &>/dev/null || true
    "$q" org.kde.KWin /KWin org.kde.KWin.reconfigure &>/dev/null || true
    sleep 2
  }
  ok "Acrylic Glass unloaded for safe upgrade"

  if sudo cp "$effect_so" "${dest_effect}.tmp" && sudo mv -f "${dest_effect}.tmp" "$dest_effect" && \
     sudo cp "$config_so" "${dest_config}.tmp" && sudo mv -f "${dest_config}.tmp" "$dest_config" 2>/dev/null; then
    ok "Acrylic Glass installed"
    # write clean preset
    local grp="Effect-liquidglass"
    kwriteconfig6 --file kwinrc --group "$grp" --key BevelStrength       0.22  2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key BlurDecorations     true  2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key BlurStrength        3     2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key BorderWidth         32    2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key BottomCornerRadius  22    2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key Brightness          1.0   2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key Contrast            1.0   2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key DialogCornerRadius  14    2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key DockCornerRadius    20    2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key EdgeBandFactor      0.24  2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key EdgeLighting        false 2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key ExcludeDocks        true  2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key GlassInactiveWindows true 2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key GlassThickness      0.2   2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key GlowColor           "#00000000" 2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key HighlightStrength   0.30  2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key HighlightWidth      24    2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key InnerShadowStrength 0.2   2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key IridescenceStrength 0.1   2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key MagnifyGlassStrength 0.03 2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key MenuCornerRadius    0     2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key NoiseStrength       2     2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key PopupCornerRadius   6     2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key RefractionEdgeSize  0     2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key RefractionNormalPow 6     2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key RefractionRGBFringing 0   2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key RefractionStrength  0     2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key RefractionWidth     96    2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key RgbRinging          12    2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key RimStrength         0.5   2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key RimWidth            32    2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key Saturation          1.0   2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key ShadowStrength      2.50  2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key SpectralMix         1     2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key SpecularStrength    0.08  2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key TintColor           "#00000000" 2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key TooltipCornerRadius 14    2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key WindowCornerRadius  22    2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key BlurMatching        false 2>/dev/null || true
    kwriteconfig6 --file kwinrc --group "$grp" --key BlurNonMatching     true  2>/dev/null || true
    ok "Acrylic Glass preset installed"
    kwriteconfig6 --file kwinrc --group Plugins --key liquidglassEnabled true 2>/dev/null || true
    ok "Acrylic Glass installed (active after Plasma restart)"
  else
    warn "Acrylic Glass built but install failed (needs sudo)"
    info "Run manually:"
    echo "    sudo cp $effect_so $dest_effect"
    echo "    sudo cp $config_so $dest_config"
  fi
}

uninstall() {
  local q
  q=$(qdbus_cmd) && "$q" org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect liquidglass &>/dev/null || true
  kwriteconfig6 --file kwinrc --group Plugins --key liquidglassEnabled false 2>/dev/null || true

  local plugin_dir
  plugin_dir=$(qmake6 -query QT_INSTALL_PLUGINS 2>/dev/null \
    || qtpaths6 --plugin-dir 2>/dev/null \
    || echo "/usr/lib/qt6/plugins")
  for so in "$plugin_dir/kwin/effects/plugins/liquidglass.so" "$plugin_dir/kwin/effects/configs/kwin_liquidglass_config.so"; do
    [[ -f "$so" ]] && sudo rm -f "$so" 2>/dev/null && ok "$(basename "$so")"
  done
  info "Acrylic Glass removed"
}
