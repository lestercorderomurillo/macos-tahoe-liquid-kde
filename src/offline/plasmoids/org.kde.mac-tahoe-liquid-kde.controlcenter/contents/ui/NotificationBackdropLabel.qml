// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.mac.tahoe.launcher as Native
import org.kde.kirigami as Kirigami

ControlLabel {
    id: label
    property bool floating: false
    property color backdropColor: "transparent"
    Native.GlassSettings { id: inkSettings; component: "notifications" }
    color: {
        const base = Kirigami.Theme.textColor;
        if (!floating || !inkSettings.dynamicTinting) return base;
        inkSettings.inkRevision;
        return inkSettings.animatedNotificationForeground(label, label.Window.window, base, backdropColor, Qt.rgba(0,0,0,0));
    }
    font.family: "SF Pro Display"; font.pixelSize: 13
}
