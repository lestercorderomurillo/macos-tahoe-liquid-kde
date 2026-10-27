#!/bin/sh
# kconf_update helper: scrub MacTahoe / Liquid leftovers from kdedefaults.
# Cleanup is valid only inside an explicit installer/uninstaller transaction.
# At login these values can be the active theme's only persisted defaults:
# KConfig removes matching per-user overrides. Never scrub them at login,
# including when an older installed .upd descriptor still invokes this helper.

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

exit 0
