#!/usr/bin/env bash
# MacTahoe Liquid KDE — GTK theme step

SRC_DIR="$OFFLINE/gtk"
DEST_DIR="$HOME/.themes"

install() {
  if [[ ! -d "$SRC_DIR" ]]; then
    fail "GTK theme source not found at $SRC_DIR"
    return 1
  fi

  mkdir -p "$DEST_DIR"
  local n_inst=0 n_re=0
  for variant in MacTahoeLiquidKde-Light MacTahoeLiquidKde-Dark; do
    [[ -d "$SRC_DIR/$variant" ]] || continue
    local existed=false
    [[ -d "$DEST_DIR/$variant" ]] && existed=true
    cp -rf "$SRC_DIR/$variant" "$DEST_DIR/"
    if [[ -d "$DEST_DIR/$variant" ]]; then
      if $existed; then
        reinstall "$variant"; n_re=$((n_re+1))
      else
        ok "$variant (installed)"; n_inst=$((n_inst+1))
      fi
    else
      fail "$variant (copy failed)"
    fi
  done
  # NEVER write to ~/.config/gtk-4.0/ — KDE's plasma-integration manages it
  info "$((n_inst+n_re)) GTK themes — $n_inst installed, $n_re reinstalled"
}

uninstall() {
  local n=0
  for variant in MacTahoeLiquidKde-Light MacTahoeLiquidKde-Dark; do
    [[ -d "$DEST_DIR/$variant" ]] || continue
    rm -rf "$DEST_DIR/$variant" 2>/dev/null && ok "$variant removed" && n=$((n+1)) || fail "$variant"
  done

  rm -rf "$HOME/.config/gtk-4.0/assets" "$HOME/.config/gtk-4.0/windows-assets" 2>/dev/null
  rm -f "$HOME/.config/gtk-4.0/gtk.css" "$HOME/.config/gtk-4.0/gtk-dark.css" \
        "$HOME/.config/gtk-4.0/gtk-Dark.css" "$HOME/.config/gtk-4.0/gtk-Light.css" 2>/dev/null

  local q
  q=$(qdbus_cmd) && "$q" org.kde.GtkConfig /GtkConfig org.kde.GtkConfig.setGtkTheme "Breeze" &>/dev/null || true
  command -v gsettings &>/dev/null && {
    gsettings reset org.gnome.desktop.interface gtk-theme &>/dev/null || true
    gsettings reset org.gnome.desktop.interface color-scheme &>/dev/null || true
  }
  info "$n GTK themes removed"
}
