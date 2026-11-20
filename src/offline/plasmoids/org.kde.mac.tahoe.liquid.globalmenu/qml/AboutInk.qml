// SPDX-License-Identifier: GPL-2.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import org.kde.mac.tahoe.launcher as NativeGlass

QtObject {
    id: ink
    required property Window window
    readonly property NativeGlass.PopupBackdrop sampler: NativeGlass.PopupBackdrop { window: ink.window }
    required property color preferred
    required property color fill
    required property bool tintEnabled
    readonly property bool sampled: tintEnabled && window !== null
    readonly property color foreground: sampled && sampler.backdropRevision > 0
        ? sampler.animatedForegroundAt(window.contentItem, Qt.point(window.width / 2, window.height / 2),
                               Qt.size(window.width / 4, window.height / 9), preferred, fill)
        : preferred

    function windowMoveStarted() { sampler.windowMoveStarted(); }

    function withOpacity(fallback: color): color {
        return sampled ? Qt.rgba(foreground.r, foreground.g, foreground.b, fallback.a) : fallback;
    }
}
