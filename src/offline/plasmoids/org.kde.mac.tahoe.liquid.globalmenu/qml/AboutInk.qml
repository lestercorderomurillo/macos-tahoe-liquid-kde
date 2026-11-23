// SPDX-License-Identifier: GPL-2.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import org.kde.mac.tahoe.launcher as NativeGlass

QtObject {
    id: ink
    required property Window window
    readonly property NativeGlass.PopupBackdrop sampler: NativeGlass.PopupBackdrop {
        window: ink.window
    }
    required property color preferred
    required property color fill
    required property bool tintEnabled
    function foregroundFor(item, base = preferred) {
        return tintEnabled ? NativeGlass.AdaptiveContrast.foreground(sampler, item, base, fill) : base;
    }
}
