// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.plasma.core as PlasmaCore
import org.kde.mac.tahoe.launcher as Native

PlasmaCore.Dialog {
    id: popup
    required property var surfaces
    type: PlasmaCore.Dialog.AppletPopup
    flags: Qt.WindowStaysOnTopHint
    backgroundHints: PlasmaCore.Dialog.NoBackground
    hideOnWindowDeactivate: true

    // The theme supplies the base colour in both modes.
    property Native.GlassSettings inkSettings: Native.GlassSettings { window: popup }
    readonly property bool adaptiveForeground: inkSettings.dynamicTinting
    // When false, the whole window takes pointer input (not only the glass islands).
    property bool inputOnGlassOnly: true
    function foregroundFor(item: Item, base: color): color {
        if (!adaptiveForeground) return base;
        let tile = item;
        while (tile && tile.fillColor === undefined) tile = tile.parent;
        return Native.AdaptiveContrast.resolve(glass, item, base, tile?.fillColor ?? "transparent",
                "controlcenter.tile", tile, glass.window?.contentItem, item.Kirigami.Theme.textColor);
    }
    property Native.ControlGlass glass: Native.ControlGlass {
        window: popup
        surfaces: popup.surfaces
        maskWindow: popup.inputOnGlassOnly
    }
}
