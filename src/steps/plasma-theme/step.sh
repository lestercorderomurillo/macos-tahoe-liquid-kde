#!/usr/bin/env bash
# MacTahoe Liquid KDE — plasma theme step

SRC_DIR="$OFFLINE/plasma-theme"
DEST_DIR="$HOME/.local/share/plasma/desktoptheme"

install() {
  if [[ ! -d "$SRC_DIR" ]]; then
    fail "Plasma theme source not found at $SRC_DIR"
    return 1
  fi

  mkdir -p "$DEST_DIR"
  local n_inst=0 n_re=0
  for variant in MacTahoeLiquidKde-Dark MacTahoeLiquidKde-Light; do
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
  info "$((n_inst+n_re)) Plasma themes — $n_inst installed, $n_re reinstalled"
}

uninstall() {
  local n=0
  for variant in MacTahoeLiquidKde-Dark MacTahoeLiquidKde-Light; do
    local dir="$DEST_DIR/$variant"
    [[ -d "$dir" ]] || continue
    rm -rf "$dir" 2>/dev/null && ok "$variant removed" && n=$((n+1)) || fail "$variant"
  done
  if command -v kwriteconfig6 &>/dev/null; then
    kwriteconfig6 --file plasmarc --group Theme --key name "default" 2>/dev/null || true
  fi
  info "$n Plasma themes removed"
}
