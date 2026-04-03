#!/usr/bin/env bash
# MacTahoe Liquid KDE — icons step

DEST="$STEPS/icons"
DEST_DIR="$HOME/.local/share/icons"
MIRROR_FILE="$SRC/mirrors/icons.json"

deps() {
  echo "curl"
  echo "unzip"
}

# ── assemble default + dark icon themes from extracted repo ──────
assemble() {
  local repo="$1" name="$2"

  # ── default ────────────────────────────────────────────────
  local d="$DEST/$name"
  mkdir -p "$d/status"
  cp -r "$repo/src/index.theme" "$d/"
  sed -i "s/MacTahoe/$name/g" "$d/index.theme"
  cp -r "$repo/src/"{actions,animations,apps,categories,devices,emotes,emblems,mimes,places,preferences} "$d/"
  cp -r "$repo/src/status/"{16,22,24,32,symbolic} "$d/status/"
  cp -r "$repo/links/"{actions,apps,categories,devices,emotes,emblems,mimes,places,status,preferences} "$d/"
  rm -f "$d/places/scalable/user-trash"{,-full}"-dark.svg"
  ( cd "$d" && for c in actions animations apps categories devices emotes emblems mimes places preferences status; do
      ln -sf "$c" "${c}@2x"; done )

  # ── dark ───────────────────────────────────────────────────
  local dk="$DEST/${name}-dark"
  mkdir -p "$dk"/{actions,apps,categories,emblems,devices,mimes,places,status}
  cp -r "$repo/src/index.theme" "$dk/"
  sed -i "s/MacTahoe/${name}-dark/g" "$dk/index.theme"
  sed -i "s/^Inherits=.*/Inherits=$name,hicolor,breeze/" "$dk/index.theme"
  cp -r "$repo/src/actions"                               "$dk/"
  cp -r "$repo/src/apps/"{16,22,32,symbolic}              "$dk/apps/"
  cp -r "$repo/src/categories/"{22,symbolic}              "$dk/categories/"
  cp -r "$repo/src/emblems/symbolic"                      "$dk/emblems/"
  cp -r "$repo/src/mimes/symbolic"                        "$dk/mimes/"
  cp -r "$repo/src/devices/"{16,22,24,32,symbolic}        "$dk/devices/"
  cp -r "$repo/src/places/"{16,22,24,scalable,symbolic}   "$dk/places/"
  cp -r "$repo/src/status/symbolic"                       "$dk/status/"
  find "$dk" -name "*.svg" -exec sed -i 's/#363636/#dedede/g' {} +
  mv -f "$dk/places/scalable/user-trash-dark.svg"         "$dk/places/scalable/user-trash.svg"      2>/dev/null || true
  mv -f "$dk/places/scalable/user-trash-full-dark.svg"    "$dk/places/scalable/user-trash-full.svg" 2>/dev/null || true
  cp -r "$repo/links/actions/"{16,22,24,32,symbolic}      "$dk/actions/"
  cp -r "$repo/links/devices/"{16,22,24,32,symbolic}      "$dk/devices/"
  cp -r "$repo/links/places/"{16,22,24,scalable,symbolic} "$dk/places/"
  cp -r "$repo/links/apps/"{16,22,32,symbolic}            "$dk/apps/"
  cp -r "$repo/links/categories/"{22,symbolic}            "$dk/categories/"
  cp -r "$repo/links/mimes/symbolic"                      "$dk/mimes/"
  cp -r "$repo/links/status/symbolic"                     "$dk/status/"
  ( cd "$DEST" && \
    ln -sf "../$name/animations"              "${name}-dark/animations"          && \
    ln -sf "../$name/emotes"                  "${name}-dark/emotes"              && \
    ln -sf "../$name/preferences"             "${name}-dark/preferences"         && \
    ln -sf "../../$name/categories/32"        "${name}-dark/categories/32"       && \
    ln -sf "../../$name/apps/scalable"        "${name}-dark/apps/scalable"       && \
    ln -sf "../../$name/devices/scalable"     "${name}-dark/devices/scalable"    && \
    for sz in 16 22 24 32;     do ln -sf "../../$name/status/$sz"  "${name}-dark/status/$sz";  done && \
    for sz in 16 22 24;        do ln -sf "../../$name/emblems/$sz" "${name}-dark/emblems/$sz"; done && \
    for sz in 16 22 scalable;  do ln -sf "../../$name/mimes/$sz"   "${name}-dark/mimes/$sz";   done )
  ( cd "$dk" && for c in actions animations apps categories devices emotes emblems mimes places preferences status; do
      ln -sf "$c" "${c}@2x"; done )
}

download() {
  TMP="/tmp/tahoe-icons-$$"
  trap 'rm -rf "$TMP"' RETURN
  mkdir -p "$TMP"

  rm -rf "$DEST"/MacTahoeLiquidKde-Icons*
  mkdir -p "$DEST"

  local any_ok=false

  handle_mirror() {
    local xdir="$1" prefix="$2"
    local repo
    repo=$(find "$xdir" -maxdepth 2 -name "src" -type d | head -1)
    repo="${repo%/src}"
    [[ -d "$repo/src" && -d "$repo/links" ]] || return 1
    assemble "$repo" "$prefix"
  }

  run_mirrors "$MIRROR_FILE" 0 && any_ok=true

  $any_ok || { fail "no icon themes installed — all mirrors failed"; return 1; }
}

install() {
  # snapshot before
  declare -A pre=()
  for d in "$DEST_DIR"/*/; do [[ -d "$d" ]] && pre["$(basename "$d")"]=1; done

  mkdir -p "$DEST_DIR"
  local n_inst=0 n_re=0
  for theme in "$DEST"/Mac*/; do
    [[ -d "$theme" ]] || continue
    local name
    name=$(basename "$theme")
    [[ -f "$theme/index.theme" ]] || { fail "$name (no index.theme — skipping)"; continue; }

    if safe_copy "$theme" "$DEST_DIR/$name"; then
      if [[ -n "${pre[$name]+_}" ]]; then
        reinstall "$name"; n_re=$((n_re+1))
      else
        ok "$name (installed)"; n_inst=$((n_inst+1))
      fi
    else
      fail "$name (copy failed)"
    fi
  done

  # ensure dark theme inherits from light
  local dark_idx="$DEST_DIR/MacTahoeLiquidKde-Icons-dark/index.theme"
  if [[ -f "$dark_idx" ]] && ! grep -q "Inherits=MacTahoeLiquidKde-Icons," "$dark_idx"; then
    sed -i 's/^Inherits=.*/Inherits=MacTahoeLiquidKde-Icons,hicolor,breeze/' "$dark_idx"
  fi

  # rebuild icon caches
  for theme in "$DEST_DIR"/MacTahoeLiquidKde-Icons*/; do
    [[ -d "$theme" ]] || continue
    command -v gtk-update-icon-cache &>/dev/null && gtk-update-icon-cache -f -t "$theme" 2>/dev/null || true
  done

  local n=$(( n_inst + n_re ))
  [[ $n -eq 1 ]] && info "1 icon theme — $n_inst installed, $n_re reinstalled" \
                  || info "$n icon themes — $n_inst installed, $n_re reinstalled"
}

uninstall() {
  local n=0
  for theme in "$DEST_DIR"/MacTahoeLiquidKde-Icons*; do
    [[ -d "$theme" ]] || continue
    local name
    name=$(basename "$theme")
    rm -rf "$theme" 2>/dev/null && ok "$name" && n=$((n+1)) || fail "$name"
  done
  info "$n icon themes removed"
}
