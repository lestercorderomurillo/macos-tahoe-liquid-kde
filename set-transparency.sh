#!/usr/bin/env bash
# MacTahoe Liquid KDE — set global background transparency
# Usage: bash set-transparency.sh <percent> [--apply]
#
# Examples:
#   bash set-transparency.sh 60          # set to 60%, don't apply
#   bash set-transparency.sh 75 --apply  # set to 75% and install to live system
#
# Does NOT touch buttons, text, shadows, or highlight colors.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KVANTUM="$REPO/src/offline/kvantum/mac-tahoe-liquid-kde"
PLASMA="$REPO/src/offline/plasma-theme"

if [[ $# -lt 1 ]] || [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
  echo "Usage: bash set-transparency.sh <percent> [--apply]"
  echo ""
  echo "  <percent>   Background opacity 0–100 (e.g. 60 = 60% opaque)"
  echo "  --apply     Also install to live system and restart plasmashell"
  exit 0
fi

PCT="$1"
APPLY=false
[[ "${2:-}" == "--apply" ]] && APPLY=true

if ! [[ "$PCT" =~ ^[0-9]+$ ]] || (( PCT < 0 || PCT > 100 )); then
  echo "Error: percent must be 0–100"
  exit 1
fi

# ── derived values ──────────────────────────────────────────────
# Kvantum reduce_menu_opacity: reduction amount (100 - target)
MENU_REDUCE=$(( 100 - PCT ))

# Kvantum color alpha: hex byte (0x00–0xFF)
ALPHA_DEC=$(( PCT * 255 / 100 ))
ALPHA_HEX=$(printf '%02X' "$ALPHA_DEC")

# Plasma SVG opacity: decimal 0.00–1.00
SVG_OPACITY=$(printf '0.%02d' "$PCT")
# Handle 100% edge case
(( PCT == 100 )) && SVG_OPACITY="1"

echo "Setting transparency to ${PCT}%"
echo "  Kvantum menu reduction: ${MENU_REDUCE}"
echo "  Kvantum color alpha: 0x${ALPHA_HEX} (${ALPHA_DEC}/255)"
echo "  Plasma SVG opacity: ${SVG_OPACITY}"
echo ""

# ── Kvantum configs ─────────────────────────────────────────────
for cfg in "$KVANTUM"/mac-tahoe-liquid-kde.kvconfig "$KVANTUM"/mac-tahoe-liquid-kdeDark.kvconfig; do
  [[ -f "$cfg" ]] || continue
  name=$(basename "$cfg")

  # reduce_menu_opacity
  sed -i "s/^reduce_menu_opacity=.*/reduce_menu_opacity=${MENU_REDUCE}/" "$cfg"

  # Color alpha: replace 2-char hex suffix on colors that have alpha
  # Match patterns like #RRGGBBAA where we only change AA
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
# Replace the main fill opacity in each SVG.
# Target pattern: opacity:X.XX;fill where X.XX was the previous value.
# We only replace values that look like main fills (0.15–0.95 range),
# not shadows (0.05, 0.06, 0.1) or hint rects (0.875).
for variant in MacTahoeLiquidKde-Dark MacTahoeLiquidKde-Light; do
  for svg in widgets/translucentbackground widgets/panel-background widgets/tooltip dialogs/background; do
    file="$PLASMA/$variant/${svg}.svgz"
    [[ -f "$file" ]] || continue
    tmp=$(mktemp)
    gunzip -c "$file" > "$tmp"

    # Replace fill opacities in the 0.15–0.95 range (main fills)
    sed -i -E "s/opacity:0\.(1[5-9]|[2-8][0-9]|9[0-5]);fill/opacity:${SVG_OPACITY};fill/g" "$tmp"

    gzip -c "$tmp" > "$file"
    rm -f "$tmp"
    echo "  ✓ $variant/$svg"
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
  echo "  ✓ Files copied"
  echo "  Restarting plasmashell..."
  plasmashell --replace &>/dev/null &
  disown
  echo "  ✓ Done"
fi
