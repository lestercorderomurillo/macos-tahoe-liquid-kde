#!/usr/bin/env bash
# MacTahoe Liquid KDE — plasmoids step

SRC_DIR="$OFFLINE/plasmoids"
DEST_DIR="$HOME/.local/share/plasma/plasmoids"

install() {
  mkdir -p "$DEST_DIR"
  local n_inst=0 n_re=0
  for widget in "$SRC_DIR"/*/; do
    [[ -d "$widget" ]] || continue
    local name
    name=$(basename "$widget")
    # skip globalmenu — handled by its own step
    [[ "$name" == *globalmenu* ]] && continue
    [[ -f "$widget/metadata.json" ]] || { fail "$name (no metadata.json — skipping)"; continue; }

    local was_present=false
    [[ -d "$DEST_DIR/$name" ]] && was_present=true

    if safe_copy "$widget" "$DEST_DIR/$name"; then
      if $was_present; then
        reinstall "$name"; n_re=$((n_re+1))
      else
        ok "$name (installed)"; n_inst=$((n_inst+1))
      fi
    else
      fail "$name (copy failed)"
    fi
  done
  local n=$(( n_inst + n_re ))
  [[ $n -eq 1 ]] && info "1 plasmoid — $n_inst installed, $n_re reinstalled" \
                  || info "$n plasmoids — $n_inst installed, $n_re reinstalled"
}

uninstall() {
  local n=0
  for widget in "$DEST_DIR"/org.kde.mac-tahoe-liquid-kde.* "$DEST_DIR"/org.kde.mactahoe-liquid-kde.*; do
    [[ -d "$widget" ]] || continue
    local name
    name=$(basename "$widget")
    rm -rf "$widget" 2>/dev/null && ok "$name" && n=$((n+1)) || fail "$name"
  done
  info "$n plasmoids removed"
}
