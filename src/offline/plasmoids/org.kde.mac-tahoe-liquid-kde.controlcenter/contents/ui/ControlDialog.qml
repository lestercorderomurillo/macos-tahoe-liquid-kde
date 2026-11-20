// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.core as PlasmaCore
import org.kde.mac.tahoe.launcher as Native

PlasmaCore.Dialog {
    id: popup
    required property var surfaces
    type: PlasmaCore.Dialog.AppletPopup
    flags: Qt.WindowStaysOnTopHint
    backgroundHints: PlasmaCore.Dialog.NoBackground
    hideOnWindowDeactivate: true

    // When false, text and symbols keep the theme colour instead of switching
    // to dark over a bright backdrop.
    property Native.GlassSettings inkSettings: Native.GlassSettings { window: popup }
    readonly property bool adaptiveForeground: inkSettings.dynamicTinting
    // When false, the whole window takes pointer input (not only the glass islands).
    property bool inputOnGlassOnly: true
    function foregroundFor(item: Item, base: color): color {
        if (!adaptiveForeground) return base;
        glass.backdropRevision; // Re-evaluate when the compositor samples a new frame.
        const point = item.mapToItem(popup.contentItem, item.width / 2, item.height / 2);
        let tile = item;
        while (tile && tile.fillColor === undefined) tile = tile.parent;
        const fill = tile ? tile.fillColor : Qt.rgba(0, 0, 0, 0);
        const radius = Qt.size(Math.min(36, (tile || item).width / 3), Math.min(64, (tile || item).height / 2));
        return glass.animatedForegroundAt(item, point, radius, base, fill);
    }
    property Native.ControlGlass glass: Native.ControlGlass {
        window: popup
        surfaces: popup.surfaces
        maskWindow: popup.inputOnGlassOnly
    }
}
