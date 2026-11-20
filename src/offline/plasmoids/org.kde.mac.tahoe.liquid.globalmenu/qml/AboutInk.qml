// SPDX-License-Identifier: GPL-2.0-or-later
import QtQuick
import org.kde.mac.tahoe.launcher as NativeGlass

NativeGlass.PopupBackdrop {
    id: ink
    required property color preferred
    required property color fill
    required property bool tintEnabled
    readonly property bool sampled: tintEnabled && backdropRevision > 0 && window !== null
    readonly property color foreground: sampled
        ? animatedForegroundAt(window, Qt.point(window.width / 2, window.height / 2),
                               Qt.size(window.width / 4, window.height / 9), preferred, fill)
        : preferred

    function withOpacity(fallback: color): color {
        return sampled ? Qt.rgba(foreground.r, foreground.g, foreground.b, fallback.a) : fallback;
    }
}
