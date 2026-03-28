#!/usr/bin/env bash
# MacTahoe Liquid KDE — step-icons (online installer step)
# mirrors documented in src/mirrors/icons.txt
set -uo pipefail

DEST="$(pwd)/src/steps/icons"
TMP="/tmp/tahoe-icons-$$"

source "$(dirname "$0")/utils.sh"

[[ -d "src" ]] || { echo -e "\033[0;31m  run from repo root.\033[0m" >&2; exit 1; }
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP"

rm -rf "$DEST"/MacTahoeLiquidKde-Icons*
mkdir -p "$DEST"

# ── assemble default + dark icon themes from extracted repo ───
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

# ── download, extract, assemble ───────────────────────────────
any_ok=false
i=0
mapfile -t MIRRORS < <(grep '^mirror:' "src/mirrors/icons.txt" | sed 's/^mirror: *//')

for entry in "${MIRRORS[@]}"; do
  IFS='|' read -r url ext name <<< "$entry"
  ((i++))
  out="$TMP/mirror${i}.${ext}"
  xdir="$TMP/extract${i}"

  fetch "$url" "$out"    || continue
  extract "$out" "$xdir" || continue

  repo=$(find "$xdir" -maxdepth 2 -name "src" -type d | head -1)
  repo="${repo%/src}"
  [[ -d "$repo/src" && -d "$repo/links" ]] || continue

  assemble "$repo" "$name" && { ok "mirror $i"; any_ok=true; break; }
done

$any_ok || { fail "no icon themes installed — all mirrors failed"; exit 1; }
