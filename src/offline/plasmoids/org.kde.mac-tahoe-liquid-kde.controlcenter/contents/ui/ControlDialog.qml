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

    // When false, text and symbols keep the theme colour instead of switching
    // to dark over a bright backdrop.
    property bool adaptiveForeground: true
    property bool regionalForeground: false
    // When false, the whole window takes pointer input (not only the glass islands).
    property bool inputOnGlassOnly: true
    function foregroundFor(item: Item, base: color): color {
        if (!adaptiveForeground) return base;
        glass.backdropRevision; // Re-evaluate when the compositor samples a new frame.
        const point = item.mapToItem(popup.contentItem, item.width / 2, item.height / 2);
        let tile = item;
        while (tile && tile.fillColor === undefined) tile = tile.parent;
        const fill = tile ? tile.fillColor : Qt.rgba(0, 0, 0, 0);
        const center = glass.backdropAt(point);
        if (!regionalForeground || !center.a)
            return Contrast.foreground(base, center, fill);

        const dx = Math.min(36, (tile || item).width / 3);
        const dy = Math.min(28, (tile || item).height / 3);
        function lightness(x, y) {
            return Contrast.luminance(Qt.tint(glass.backdropAt(Qt.point(x, y)), fill));
        }
        const local = Contrast.luminance(Qt.tint(center, fill));
        const nearby = (lightness(point.x - dx, point.y) + lightness(point.x + dx, point.y)
                      + lightness(point.x, point.y - dy) + lightness(point.x, point.y + dy)) / 4;
        const level = 0.65 * local + 0.35 * nearby;
        // Start with a gradual transition, then pull the tone toward the
        // readable endpoint if a sharp background edge crosses this label.
        const t = Math.max(0, Math.min(1, (level - 0.09) / 0.22));
        let tone = 0.98 - 0.92 * t * t * (3 - 2 * t);
        const white = Contrast.ratio(1, local) > Contrast.ratio(0, local);
        const limit = white ? (local + 0.05) * 4.5 - 0.05 : (local + 0.05) / 4.5 - 0.05;
        const channel = limit <= 0.0031308 ? 12.92 * limit : 1.055 * Math.pow(limit, 1 / 2.4) - 0.055;
        tone = white ? Math.max(tone, channel) : Math.min(tone, channel);
        tone = Math.max(0, Math.min(1, tone));
        return Qt.rgba(tone, tone, tone, base.a);
    }
    property Native.ControlGlass glass: Native.ControlGlass {
        window: popup
        surfaces: popup.surfaces
        maskWindow: popup.inputOnGlassOnly
    }
}
