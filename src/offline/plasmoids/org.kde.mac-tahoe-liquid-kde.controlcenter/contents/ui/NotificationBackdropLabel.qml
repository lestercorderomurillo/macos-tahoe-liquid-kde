// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.mac.tahoe.launcher as Native
import "NotificationContrast.js" as Contrast
import org.kde.kirigami as Kirigami

ControlLabel {
    id: label
    property color componentInk: "transparent"
    property bool floating: false
    property color backdropColor: "transparent"
    Native.GlassSettings { id: inkSettings; component: "notifications" }
    color: {
        const base = Contrast.preferredText(Kirigami.Theme.textColor);
        if (!floating || !inkSettings.dynamicTinting) return base;
        inkSettings.inkRevision;
        return inkSettings.animatedNotificationForeground(label, label.Window.window, base, backdropColor, Qt.rgba(0,0,0,0), componentInk);
    }
    font.family: "SF Pro Display"; font.pixelSize: 13
}
