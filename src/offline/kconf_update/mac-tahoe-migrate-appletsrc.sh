#!/bin/sh
# kconf_update helper: rewrite old dock applet IDs to the MacTahoe dock fork
# in plasma-org.kde.plasma.desktop-appletsrc. kconf_update passes the config
# file as $1; the installer also runs this directly when the kconf_update
# binary is missing. Mirrors the old plasmoids._APPLETSRC_RENAMES behaviour.
[ -f "$1" ] || exit 0

sed -i \
    -e 's/org\.kde\.plasma\.icontasks/org.kde.mac.tahoe.liquid.icontasks/g' \
    -e 's/org\.kde\.plasma\.taskmanager/org.kde.mac.tahoe.liquid.taskmanager/g' \
    -e 's/org\.kde\.mac-tahoe-liquid-kde\.icontasks/org.kde.mac.tahoe.liquid.icontasks/g' \
    -e 's/org\.kde\.mac-tahoe-liquid-kde\.taskmanager/org.kde.mac.tahoe.liquid.taskmanager/g' \
    "$1"
exit 0
