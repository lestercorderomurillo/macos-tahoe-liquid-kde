#!/usr/bin/env bash
# MacTahoe Liquid KDE — color schemes step

SRC_DIR="$OFFLINE/color-schemes"
DEST_DIR="$HOME/.local/share/color-schemes"

install() {
  if [[ ! -d "$SRC_DIR" ]]; then
    fail "Color scheme source not found at $SRC_DIR"
    return 1
  fi

  mkdir -p "$DEST_DIR"
  local n_inst=0 n_re=0
  for cs in "$SRC_DIR"/*.colors; do
    [[ -f "$cs" ]] || continue
    local name existed=false
    name=$(basename "$cs" .colors)
    [[ -f "$DEST_DIR/$(basename "$cs")" ]] && existed=true
    cp -f "$cs" "$DEST_DIR/"
    if $existed; then
      reinstall "$name"; n_re=$((n_re+1))
    else
      ok "$name (installed)"; n_inst=$((n_inst+1))
    fi
  done
  info "$((n_inst+n_re)) color schemes — $n_inst installed, $n_re reinstalled"
}

uninstall() {
  local n=0
  for cs in "$DEST_DIR"/MacTahoeLiquidKde*.colors; do
    [[ -f "$cs" ]] || continue
    local name
    name=$(basename "$cs" .colors)
    rm -f "$cs" 2>/dev/null && ok "$name removed" && n=$((n+1)) || fail "$name"
  done
  info "$n color schemes removed"
}
