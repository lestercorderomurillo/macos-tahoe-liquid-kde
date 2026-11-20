// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.core as PlasmaCore
import org.kde.mac.tahoe.launcher as Native
import "NotificationContrast.js" as Contrast

PlasmaCore.Dialog {
    id: popup
    required property var surfaces
    type: PlasmaCore.Dialog.AppletPopup
    flags: Qt.WindowStaysOnTopHint
    backgroundHints: PlasmaCore.Dialog.NoBackground
    hideOnWindowDeactivate: true

    function foregroundFor(item: Item, base: color): color {
        glass.backdropRevision; // Re-evaluate when the compositor samples a new frame.
        const point = item.mapToItem(popup.contentItem, item.width / 2, item.height / 2);
        let tile = item;
        while (tile && tile.fillColor === undefined) tile = tile.parent;
        return Contrast.foreground(base, glass.backdropAt(point), tile ? tile.fillColor : Qt.rgba(0, 0, 0, 0));
    }
    property Native.ControlGlass glass: Native.ControlGlass {
        window: popup
        surfaces: popup.surfaces
    }
}
