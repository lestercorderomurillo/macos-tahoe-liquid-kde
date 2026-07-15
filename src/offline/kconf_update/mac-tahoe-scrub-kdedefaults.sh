#!/bin/sh
# kconf_update helper: scrub MacTahoe / Liquid leftovers from kdedefaults.
# KF6 kconf_update runs scripts with no arguments, so argless it walks the
# kdedefaults files under $XDG_CONFIG_HOME itself; the installer and tests
# pass one explicit file instead. Mirrors apply._scrub_kdedefaults.

scrub() {
    f=$1
    [ -f "$f" ] || return 0
    # Only touch files that still reference MacTahoe / Liquid.
    grep -Eqi 'mac[-.]?tahoe|liquid' "$f" || return 0
    if [ "$(basename "$f")" = "package" ]; then
        printf 'org.kde.breeze.desktop\n' > "$f"
        return 0
    fi
    tmp=$(mktemp) || return 0
    grep -Ev '^(ColorScheme|Theme|name|cursorTheme|theme|library)[[:space:]]*=.*(mac[-.]?tahoe|MacTahoe|liquid)' "$f" > "$tmp" || :
    cat "$tmp" > "$f"   # cat, not mv: keeps the file's owner and mode
    rm -f "$tmp"
}

if [ -n "$1" ]; then
    scrub "$1"
    exit 0
fi

base="${XDG_CONFIG_HOME:-$HOME/.config}/kdedefaults"
for fn in package kdeglobals plasmarc kcminputrc kwinrc ksplashrc kscreenlockerrc; do
    scrub "$base/$fn"
done
exit 0
