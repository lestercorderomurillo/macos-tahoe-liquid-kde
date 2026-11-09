// SPDX-License-Identifier: GPL-3.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid

Item {
    id: host
    required property string pluginId
    property Item appletItem: null
    implicitWidth: appletItem ? Math.max(appletItem.implicitWidth, appletItem.Layout.minimumWidth, 0) : 0
    implicitHeight: appletItem ? Math.max(appletItem.implicitHeight, appletItem.Layout.minimumHeight, 0) : 0
    Layout.minimumWidth: implicitWidth
    Layout.fillHeight: true
    Component.onCompleted: {
        appletItem = Plasmoid.accessory(pluginId)
        if (appletItem) {
            appletItem.parent = host
            appletItem.anchors.fill = host
            appletItem.visible = true
        }
    }
    Component.onDestruction: {
        // Plasma owns the applet and its configuration across representation changes.
        if (appletItem) {
            appletItem.visible = false
            appletItem.parent = null
        }
    }
}
