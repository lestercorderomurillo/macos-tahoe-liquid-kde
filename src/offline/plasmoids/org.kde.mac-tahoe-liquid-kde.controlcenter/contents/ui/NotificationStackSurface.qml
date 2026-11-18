// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Item {
    id: stack
    objectName: "notificationStackSurface"
    property int depth: 0
    property alias contentItem: surface.contentItem
    readonly property color fillColor: surface.fillColor
    readonly property real cardHeight: surface.height
    readonly property real cornerRadius: surface.cornerRadius
    readonly property var surfaces: {
        const areas = [{x:0, y:0, width:width, height:cardHeight, radius:cornerRadius}];
        for (let layer = 0; layer < depth; ++layer)
            areas.push({x:(layer+1)*4, y:cardHeight-8+layer*4,
                width:width-(layer+1)*8, height:12, radius:8});
        return areas;
    }
    implicitWidth: 344
    implicitHeight: surface.implicitHeight + depth * 4
    Repeater {
        model: stack.depth
        Item {
            required property int index
            x: (stack.depth-index)*4
            y: surface.height+(stack.depth-index-1)*4
            width: stack.width-x*2; height: 4
            clip: true
            NotificationSurface {
                y: 4-surface.height
                width: parent.width; height: surface.height
                contentItem: Item {}
            }
        }
    }
    NotificationSurface {
        id: surface
        width: parent.width; height: implicitHeight
    }
}
