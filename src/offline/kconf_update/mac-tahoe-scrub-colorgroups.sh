#!/bin/sh
# kconf_update helper: drop malformed [Colors:*] / [ColorEffects:*] headers
# (lines embedding escaped \x5d\x5b brackets) and their keys from kdeglobals.
# KF6 kconf_update runs scripts with no arguments, so argless it targets the
# live kdeglobals; the installer and tests pass an explicit file instead.
# Mirrors theme_switch._scrub_malformed_color_groups.

f=${1:-"${XDG_CONFIG_HOME:-$HOME/.config}/kdeglobals"}
[ -f "$f" ] || exit 0

tmp=$(mktemp) || exit 0
awk '
/^\[((Colors:)|(ColorEffects:)).*\\x5d\\x5b.*\]$/ { skip = 1; next }
skip && /^\[/ { skip = 0 }
skip { next }
{ print }
' "$f" > "$tmp"
cat "$tmp" > "$f"   # cat, not mv: keeps the file's owner and mode
rm -f "$tmp"
exit 0
