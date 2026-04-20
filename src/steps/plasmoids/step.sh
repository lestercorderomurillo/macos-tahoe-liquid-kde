#!/usr/bin/env bash
# MacTahoe Liquid KDE — plasmoids step

SRC_DIR="$OFFLINE/plasmoids"
DEST_DIR="$HOME/.local/share/plasma/plasmoids"
TASKMANAGER_SRC_DIR="$OFFLINE/plasmoids/org.kde.mac.tahoe.liquid.taskmanager"
TASKMANAGER_BUILD_DIR="$TASKMANAGER_SRC_DIR/build"
TASKMANAGER_DEST_SO="/usr/lib/qt6/plugins/plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so"

deps() {
  echo "cmake"
  echo "g++:gcc"
  echo "pkg-config:pkgconf"
}

build() {
  [[ -f "$TASKMANAGER_SRC_DIR/CMakeLists.txt" ]] || return 0

  rm -rf "$TASKMANAGER_BUILD_DIR"
  mkdir -p "$TASKMANAGER_BUILD_DIR"

  if cmake -S "$TASKMANAGER_SRC_DIR" -B "$TASKMANAGER_BUILD_DIR" -DCMAKE_BUILD_TYPE=Release &>/dev/null; then
    if make -C "$TASKMANAGER_BUILD_DIR" -j"$(nproc)" &>/dev/null; then
      ok "Dock Task Manager built"
    else
      fail "Dock Task Manager: build failed"
    fi
  else
    fail "Dock Task Manager: cmake configure failed"
  fi
}

install() {
  mkdir -p "$DEST_DIR"
  local custom_taskmanager="$DEST_DIR/org.kde.mac.tahoe.liquid.taskmanager"
  local legacy_taskmanager="$DEST_DIR/org.kde.mac-tahoe-liquid-kde.taskmanager"
  local legacy_icontasks="$DEST_DIR/org.kde.mac-tahoe-liquid-kde.icontasks"
  local stock_taskmanager="$DEST_DIR/org.kde.plasma.taskmanager"
  local stock_icontasks="$DEST_DIR/org.kde.plasma.icontasks"
  local appletsrc="$HOME/.config/plasma-org.kde.plasma.desktop-appletsrc"
  local taskmanager_so="$TASKMANAGER_BUILD_DIR/bin/plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so"
  if [[ -d "$custom_taskmanager" ]]; then
    rm -rf "$custom_taskmanager" 2>/dev/null && ok "org.kde.mac.tahoe.liquid.taskmanager (removed stale local package)" \
      || fail "org.kde.mac.tahoe.liquid.taskmanager (failed to remove stale local package)"
  fi
  if [[ -d "$stock_taskmanager" ]]; then
    rm -rf "$stock_taskmanager" 2>/dev/null && ok "org.kde.plasma.taskmanager (removed local stock override)" \
      || fail "org.kde.plasma.taskmanager (failed to remove local stock override)"
  fi
  if [[ -d "$stock_icontasks" ]]; then
    rm -rf "$stock_icontasks" 2>/dev/null && ok "org.kde.plasma.icontasks (removed local stock override)" \
      || fail "org.kde.plasma.icontasks (failed to remove local stock override)"
  fi
  if [[ -d "$legacy_taskmanager" ]]; then
    rm -rf "$legacy_taskmanager" 2>/dev/null && ok "org.kde.mac-tahoe-liquid-kde.taskmanager (removed legacy dock base)" \
      || fail "org.kde.mac-tahoe-liquid-kde.taskmanager (failed to remove legacy dock base)"
  fi
  if [[ -d "$legacy_icontasks" ]]; then
    rm -rf "$legacy_icontasks" 2>/dev/null && ok "org.kde.mac-tahoe-liquid-kde.icontasks (removed legacy dock wrapper)" \
      || fail "org.kde.mac-tahoe-liquid-kde.icontasks (failed to remove legacy dock wrapper)"
  fi
  if [[ -f "$appletsrc" ]] && grep -Eq 'org\.kde\.(plasma\.icontasks|plasma\.taskmanager|mac-tahoe-liquid-kde\.icontasks|mac-tahoe-liquid-kde\.taskmanager)' "$appletsrc"; then
    sed -i \
      -e 's/org\.kde\.plasma\.icontasks/org.kde.mac.tahoe.liquid.icontasks/g' \
      -e 's/org\.kde\.plasma\.taskmanager/org.kde.mac.tahoe.liquid.taskmanager/g' \
      -e 's/org\.kde\.mac-tahoe-liquid-kde\.icontasks/org.kde.mac.tahoe.liquid.icontasks/g' \
      -e 's/org\.kde\.mac-tahoe-liquid-kde\.taskmanager/org.kde.mac.tahoe.liquid.taskmanager/g' \
      "$appletsrc" \
      && ok "dock config migrated to MacTahoe dock fork" \
      || fail "dock config migration failed"
  fi
  if [[ -f "$taskmanager_so" ]]; then
    if sudo cp "$taskmanager_so" "${TASKMANAGER_DEST_SO}.tmp" && sudo mv -f "${TASKMANAGER_DEST_SO}.tmp" "$TASKMANAGER_DEST_SO"; then
      ok "org.kde.mac.tahoe.liquid.taskmanager (installed compiled dock base)"
    else
      fail "org.kde.mac.tahoe.liquid.taskmanager (failed to install compiled dock base)"
    fi
  else
    fail "org.kde.mac.tahoe.liquid.taskmanager (missing build artifact)"
  fi
  local n_inst=0 n_re=0
  for widget in "$SRC_DIR"/*/; do
    [[ -d "$widget" ]] || continue
    local name
    name=$(basename "$widget")
    # skip C++ applets — handled by their own build steps
    [[ -f "$widget/CMakeLists.txt" ]] && continue
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
  local dock_taskmanager="$DEST_DIR/org.kde.mac.tahoe.liquid.taskmanager"
  local dock_icontasks="$DEST_DIR/org.kde.mac.tahoe.liquid.icontasks"
  [[ -f "$TASKMANAGER_DEST_SO" ]] && sudo rm -f "$TASKMANAGER_DEST_SO" 2>/dev/null && ok "org.kde.mac.tahoe.liquid.taskmanager.so" && n=$((n+1))
  for widget in "$dock_taskmanager" "$dock_icontasks" "$DEST_DIR"/org.kde.mac-tahoe-liquid-kde.* "$DEST_DIR"/org.kde.mactahoe-liquid-kde.* "$DEST_DIR"/org.kde.plasma.icontasks "$DEST_DIR"/org.kde.plasma.taskmanager; do
    [[ -d "$widget" ]] || continue
    local name
    name=$(basename "$widget")
    rm -rf "$widget" 2>/dev/null && ok "$name" && n=$((n+1)) || fail "$name"
  done
  info "$n plasmoids removed"
}
