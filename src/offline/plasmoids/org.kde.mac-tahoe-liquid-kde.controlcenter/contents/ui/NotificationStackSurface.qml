// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Effects

Item {
    id: stack
    objectName: "notificationStackSurface"
    property bool panelHighlight: true
    property int depth: 0
    property alias contentItem: surface.contentItem
    readonly property color fillColor: surface.fillColor
    readonly property real cardHeight: surface.height
    readonly property real cornerRadius: surface.cornerRadius
    readonly property real layerOffset: 4
    function layerArea(level) {
        const offset = level * layerOffset;
        return {x: offset, y: offset, width: width - 2 * offset,
                height: cardHeight, radius: cornerRadius};
    }
    readonly property var surfaces: {
        const areas = [];
        for (let i = 0; i <= depth; ++i)
            areas.push(layerArea(i));
        return areas;
    }
    implicitWidth: 344
    implicitHeight: surface.implicitHeight + depth * layerOffset
    Repeater {
        model: stack.depth
        Item {
            id: lip
            required property int index
            // The Qt software scene graph cannot run a layer shader.
            readonly property bool useMask: GraphicsInfo.api !== GraphicsInfo.Software
            readonly property var area: stack.layerArea(Math.max(0, stack.depth - index))
            x: area.x
            y: area.y + area.height - height
            width: area.width
            height: useMask ? Math.min(area.height, area.radius + stack.layerOffset) : stack.layerOffset
            clip: true

            // Show the curved lip only where the card in front leaves it exposed.
            Item {
                anchors.fill: parent
                layer.enabled: lip.useMask
                layer.effect: MultiEffect {
                    maskEnabled: true
                    maskInverted: true
                    maskSource: occluder
                }
                NotificationSurface {
                    panelHighlight: stack.panelHighlight
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: lip.area.height
                    contentItem: Item {}
                }
            }
            Item {
                id: occluder
                anchors.fill: parent
                visible: false
                layer.enabled: lip.useMask
                Rectangle {
                    x: -stack.layerOffset
                    y: parent.height - height - stack.layerOffset
                    width: parent.width + 2 * stack.layerOffset
                    height: lip.area.height
                    radius: lip.area.radius
                }
            }
        }
    }
    NotificationSurface {
        panelHighlight: stack.panelHighlight
        id: surface
        width: parent.width; height: implicitHeight
    }
}
