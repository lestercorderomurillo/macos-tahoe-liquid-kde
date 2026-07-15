#!/bin/sh
# kconf_update helper: rewrite old dock applet IDs to the MacTahoe dock fork
# in plasma-org.kde.plasma.desktop-appletsrc. KF6 kconf_update runs scripts
# with no arguments, so argless it targets the live file; the installer and
# tests pass an explicit file instead. Mirrors plasmoids._APPLETSRC_RENAMES.

f=${1:-"${XDG_CONFIG_HOME:-$HOME/.config}/plasma-org.kde.plasma.desktop-appletsrc"}
[ -f "$f" ] || exit 0

sed -i \
    -e 's/org\.kde\.plasma\.icontasks/org.kde.mac.tahoe.liquid.icontasks/g' \
    -e 's/org\.kde\.plasma\.taskmanager/org.kde.mac.tahoe.liquid.taskmanager/g' \
    -e 's/org\.kde\.mac-tahoe-liquid-kde\.icontasks/org.kde.mac.tahoe.liquid.icontasks/g' \
    -e 's/org\.kde\.mac-tahoe-liquid-kde\.taskmanager/org.kde.mac.tahoe.liquid.taskmanager/g' \
    "$f"
exit 0
