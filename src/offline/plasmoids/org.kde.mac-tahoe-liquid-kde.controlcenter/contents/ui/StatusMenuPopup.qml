// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
Item {
    id: popup
    property alias panelHighlight: surface.panelHighlight
    property url source
    implicitWidth: 328
    implicitHeight: surface.implicitHeight + 20
    readonly property var surfaces: [{x: surface.x, y: surface.y, width: surface.width, height: surface.height, radius: surface.cornerRadius, fill: surface.fillColor}]
    NotificationSurface {
        id: surface
        x: 10; y: 10
        width: parent.width - 20
        cornerRadius: 16
        leftPadding: 8; rightPadding: 8
        topPadding: 8; bottomPadding: 8
        contentItem: Loader { source: popup.source }
    }
}
