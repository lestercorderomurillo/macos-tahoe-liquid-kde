#!/bin/sh
# kconf_update helper: scrub MacTahoe / Liquid leftovers from a kdedefaults
# file. kconf_update invokes this with the config file path as $1; the
# installer also runs it directly when the kconf_update binary is missing.
# Mirrors the old apply._scrub_kdedefaults regex behaviour.
[ -f "$1" ] || exit 0
base=$(basename "$1")

if [ "$base" = "package" ]; then
    printf 'org.kde.breeze.desktop\n' > "$1"
    exit 0
fi

# No MacTahoe / Liquid marker anywhere: nothing to do.
if ! grep -Eqi 'mac[-.]?tahoe|mactahoe|liquid' "$1"; then
    exit 0
fi

# Drop key lines that still point at MacTahoe / Liquid values.
tmp=$(mktemp)
grep -Evi '^(ColorScheme|Theme|name|cursorTheme|theme|library)=.*(mac|tahoe|liquid).*$' "$1" > "$tmp"
mv "$tmp" "$1"
exit 0
