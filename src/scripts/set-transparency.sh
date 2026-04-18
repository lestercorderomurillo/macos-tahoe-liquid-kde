#!/usr/bin/env bash
# MacTahoe Liquid KDE — set global background transparency
# Usage: bash set-transparency.sh <percent> [--dock <percent>] [--apply]
#
# Examples:
#   bash set-transparency.sh 60                  # everything at 60%
#   bash set-transparency.sh 75 --dock 15        # 75% general, 15% dock
#   bash set-transparency.sh 75 --apply          # same + install live, dock stays at 12%
#
# Does NOT touch buttons, text, shadows, or highlight colors.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KVANTUM="$REPO/src/offline/kvantum/mac-tahoe-liquid-kde"
PLASMA="$REPO/src/offline/plasma-theme"

if [[ $# -lt 1 ]] || [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
  cat <<'EOF'
Usage: bash set-transparency.sh <percent> [--dock <percent>] [--apply]

  <percent>          Background opacity 0–100 (e.g. 60 = 60% opaque)
  --dock <percent>   Separate opacity for the dock panel (default: 12)
  --apply            Install to live system and restart plasmashell

Examples:
  bash set-transparency.sh 60                    # everything at 60%
  bash set-transparency.sh 75 --dock 15          # 75% general, 15% dock
  bash set-transparency.sh 75 --apply            # same + install live, dock stays at 12%
EOF
  exit 0
fi

PCT="$1"; shift
DEFAULT_DOCK_PCT=12
DOCK_PCT="$DEFAULT_DOCK_PCT"
APPLY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dock)   DOCK_PCT="$2"; shift 2 ;;
    --apply)  APPLY=true; shift ;;
    *)        shift ;;
  esac
done

for v in "$PCT" "$DOCK_PCT"; do
  if ! [[ "$v" =~ ^[0-9]+$ ]] || (( v < 0 || v > 100 )); then
    echo "Error: percent must be 0–100 (got '$v')"
    exit 1
  fi
done

# ── helper: percent to SVG opacity string ───────────────────────
to_svg() {
  local p="$1"
  if (( p == 100 )); then echo "1"
  elif (( p < 10 )); then printf '0.0%d' "$p"
  else printf '0.%02d' "$p"
  fi
}

# ── derived values ──────────────────────────────────────────────
MENU_REDUCE=$(( 100 - PCT ))
ALPHA_DEC=$(( PCT * 255 / 100 ))
ALPHA_HEX=$(printf '%02X' "$ALPHA_DEC")
SVG_OPACITY=$(to_svg "$PCT")
DOCK_OPACITY=$(to_svg "$DOCK_PCT")

echo "Setting transparency"
echo "  General:  ${PCT}%  (SVG ${SVG_OPACITY}, alpha 0x${ALPHA_HEX})"
echo "  Dock:     ${DOCK_PCT}%  (SVG ${DOCK_OPACITY})"
echo "  Menu:     reduce_menu_opacity=${MENU_REDUCE}"
echo ""

# ── Kvantum configs ─────────────────────────────────────────────
for cfg in "$KVANTUM"/mac-tahoe-liquid-kde.kvconfig "$KVANTUM"/mac-tahoe-liquid-kdeDark.kvconfig; do
  [[ -f "$cfg" ]] || continue
  name=$(basename "$cfg")

  sed -i "s/^reduce_menu_opacity=.*/reduce_menu_opacity=${MENU_REDUCE}/" "$cfg"

  sed -i -E "s/(window\.color=#[0-9a-fA-F]{6})[0-9a-fA-F]{2}/\1${ALPHA_HEX}/g" "$cfg"
  sed -i -E "s/(inactive\.window\.color=#[0-9a-fA-F]{6})[0-9a-fA-F]{2}/\1${ALPHA_HEX}/g" "$cfg"
  sed -i -E "s/(base\.color=#[0-9a-fA-F]{6})[0-9a-fA-F]{2}/\1${ALPHA_HEX}/g" "$cfg"
  sed -i -E "s/(inactive\.base\.color=#[0-9a-fA-F]{6})[0-9a-fA-F]{2}/\1${ALPHA_HEX}/g" "$cfg"
  sed -i -E "s/(alt\.base\.color=#[0-9a-fA-F]{6})[0-9a-fA-F]{2}/\1${ALPHA_HEX}/g" "$cfg"
  sed -i -E "s/(inactive\.alt\.base\.color=#[0-9a-fA-F]{6})[0-9a-fA-F]{2}/\1${ALPHA_HEX}/g" "$cfg"
  sed -i -E "s/(tooltip\.base\.color=#[0-9a-fA-F]{6})[0-9a-fA-F]{2}/\1${ALPHA_HEX}/g" "$cfg"

  echo "  ✓ $name"
done

# ── Plasma SVGs ─────────────────────────────────────────────────
update_svg() {
  local file="$1" opacity="$2"
  [[ -f "$file" ]] || return
  local tmp; tmp=$(mktemp)
  gunzip -c "$file" > "$tmp"
  sed -i -E "s/opacity:(0\.585|0\.(0[5-9]|[1-8][0-9]|9[0-5]));fill/opacity:${opacity};fill/g" "$tmp"
  gzip -c "$tmp" > "$file"
  rm -f "$tmp"
}

for variant in MacTahoeLiquidKde-Dark MacTahoeLiquidKde-Light; do
  # General SVGs at main opacity
  for svg in widgets/translucentbackground widgets/tooltip dialogs/background; do
    update_svg "$PLASMA/$variant/${svg}.svgz" "$SVG_OPACITY"
    echo "  ✓ $variant/$svg → ${SVG_OPACITY}"
  done

  update_svg "$PLASMA/$variant/widgets/panel-background.svgz" "$DOCK_OPACITY"
  echo "  ✓ $variant/widgets/panel-background → ${DOCK_OPACITY} (dock)"
done

# ── GTK CSS ─────────────────────────────────────────────────────
GTK="$REPO/src/offline/gtk"
OPACITY_DEC=$(printf '0.%02d' "$PCT")
(( PCT == 100 )) && OPACITY_DEC="1"

for variant in MacTahoeLiquidKde-Light MacTahoeLiquidKde-Dark; do
  # GTK4: color-mix with @window_bg_color
  for css in "$GTK/$variant/gtk-4.0/gtk.css" "$GTK/$variant/gtk-4.0/gtk-Light.css" "$GTK/$variant/gtk-4.0/gtk-Dark.css"; do
    [[ -f "$css" ]] || continue
    sed -i -E "s/@window_bg_color [0-9]+%/@window_bg_color ${PCT}%/g" "$css"
    echo "  ✓ $(basename "$variant")/gtk-4.0/$(basename "$css") → ${PCT}%"
  done

  # GTK3: replace window bg rgba alpha and dialog alpha values
  for css in "$GTK/$variant/gtk-3.0/gtk.css"; do
    [[ -f "$css" ]] || continue
    # .background.csd background-color: rgba(R, G, B, X.XX) — just the alpha
    # Also matches .nautilus-window...background.csd lines
    sed -i -E "/\.background\.csd/,/\}/ s/(background-color: rgba\([0-9]+, [0-9]+, [0-9]+, )0\.[0-9]+/\1${OPACITY_DEC}/" "$css"
    # dialog.background.csd alpha(#hex, 0.XX)
    sed -i -E "/dialog\.background\.csd/,/\}/ s/(alpha\(#[0-9a-fA-F]+,)0\.[0-9]+/\1${OPACITY_DEC}/" "$css"
    echo "  ✓ $(basename "$variant")/gtk-3.0/gtk.css → ${OPACITY_DEC}"
  done
done

echo ""
echo "Done."

# ── apply to live system ────────────────────────────────────────
if $APPLY; then
  echo ""
  echo "Applying to live system..."
  cp -r "$KVANTUM"/* "$HOME/.config/Kvantum/mac-tahoe-liquid-kde/"
  cp -r "$PLASMA/MacTahoeLiquidKde-Dark" "$HOME/.local/share/plasma/desktoptheme/"
  cp -r "$PLASMA/MacTahoeLiquidKde-Light" "$HOME/.local/share/plasma/desktoptheme/"
  cp -r "$GTK/MacTahoeLiquidKde-Light" "$HOME/.themes/" 2>/dev/null
  cp -r "$GTK/MacTahoeLiquidKde-Dark" "$HOME/.themes/" 2>/dev/null
  echo "  ✓ Files copied"
  echo "  Restarting plasmashell..."
  plasmashell --replace &>/dev/null &
  disown
  echo "  ✓ Done"
fi
