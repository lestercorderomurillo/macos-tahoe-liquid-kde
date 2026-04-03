#!/usr/bin/env bash
# MacTahoe Liquid KDE — window decorations (aurorae) step

SRC_DIR="$OFFLINE/aurorae"
DEST_DIR="$HOME/.local/share/aurorae/themes"

install() {
  if [[ ! -d "$SRC_DIR" ]]; then
    fail "Aurorae source not found at $SRC_DIR"
    return 1
  fi

  mkdir -p "$DEST_DIR"
  local n_inst=0 n_re=0
  for mode in Dark Light; do
    local name="MacTahoeLiquidKde-${mode}"
    local dest="$DEST_DIR/$name"
    local existed=false
    [[ -d "$dest" ]] && existed=true
    mkdir -p "$dest"
    cp -f "$SRC_DIR/$name/decoration.svg" "$dest/" 2>/dev/null
    cp -f "$SRC_DIR/${name}rc" "$dest/${name}rc" 2>/dev/null
    cp -f "$SRC_DIR/icons-${mode}"/*.svg "$dest/" 2>/dev/null
    sed "s/theme_name/${name}/g" "$SRC_DIR/metadata.desktop" > "$dest/metadata.desktop"
    sed "s/theme_name/${name}/g" "$SRC_DIR/metadata.json" > "$dest/metadata.json"
    if $existed; then
      reinstall "$name"; n_re=$((n_re+1))
    else
      ok "$name (installed)"; n_inst=$((n_inst+1))
    fi
  done
  info "$((n_inst+n_re)) Aurorae themes — $n_inst installed, $n_re reinstalled"

  # apply aurorae decoration to kwinrc
  local theme_name="MacTahoeLiquidKde-Dark"
  [[ "$THEME_MODE" == "light" ]] && theme_name="MacTahoeLiquidKde-Light"
  kwriteconfig6 --file "$HOME/.config/kwinrc" --group "org.kde.kdecoration2" --key "library" "org.kde.kwin.aurorae" 2>/dev/null
  kwriteconfig6 --file "$HOME/.config/kwinrc" --group "org.kde.kdecoration2" --key "theme" "__aurorae__svg__${theme_name}" 2>/dev/null
  kwriteconfig6 --file "$HOME/.config/kwinrc" --group "org.kde.kdecoration2" --key "ButtonsOnLeft" "XIA" 2>/dev/null
  kwriteconfig6 --file "$HOME/.config/kwinrc" --group "org.kde.kdecoration2" --key "ButtonsOnRight" "" 2>/dev/null
  kwin_reconfigure
  ok "Window decoration set to ${theme_name}"
}

uninstall() {
  local n=0
  for name in MacTahoeLiquidKde-Dark MacTahoeLiquidKde-Light; do
    if [[ -d "$DEST_DIR/$name" ]]; then
      rm -rf "$DEST_DIR/$name"
      ok "$name removed"
      n=$((n+1))
    fi
  done
  if command -v kwriteconfig6 &>/dev/null; then
    kwriteconfig6 --file kwinrc --group "org.kde.kdecoration2" --key "library" "org.kde.breeze"
    kwriteconfig6 --file kwinrc --group "org.kde.kdecoration2" --key "theme" "Breeze"
    kwriteconfig6 --file kwinrc --group "org.kde.kdecoration2" --key "ButtonsOnLeft" "M"
    kwriteconfig6 --file kwinrc --group "org.kde.kdecoration2" --key "ButtonsOnRight" "IAX"
    kwin_reconfigure
    ok "Window decoration reset to Breeze"
  fi
  info "$n Aurorae themes removed"
}
