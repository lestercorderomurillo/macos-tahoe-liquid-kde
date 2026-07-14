#!/bin/sh
# kconf_update helper: drop malformed [Colors:*] / [ColorEffects:*] header
# lines from kdeglobals (lines that embed escaped brackets \x5d\x5b inside
# the group header). kconf_update passes the config file as $1; the installer
# also runs this directly when the kconf_update binary is missing.
# Mirrors the old theme_switch._scrub_malformed_color_groups behaviour.
[ -f "$1" ] || exit 0

tmp=$(mktemp)
awk '
/^\[((Colors:)|(ColorEffects:)).*\\x5d\\x5b.*\]$/ { skip = 1; next }
skip && /^\[/ { skip = 0 }
skip { next }
{ print }
' "$1" > "$tmp"
mv "$tmp" "$1"
exit 0
