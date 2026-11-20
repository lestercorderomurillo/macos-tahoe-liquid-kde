import QtQuick
import QtQuick.Controls.Basic

ScrollBar {
    id: control

    required property Flickable viewport
    // Keep the handle outside the clipped app content and its preset-specific margins.
    parent: main.parent
    anchors.right: parent.right
    anchors.rightMargin: 4
    anchors.bottom: main.bottom
    height: viewport.height
    implicitWidth: 12
    visible: viewport.visible
    z: 2
    padding: 0
    leftPadding: 9
    background: null

    contentItem: Rectangle {
        radius: width / 2
        color: main.textColor
        opacity: control.size < 1 && (control.active || control.hovered || control.pressed)
                 ? (control.pressed ? 0.44 : 0.22) : 0
        Behavior on opacity {
            NumberAnimation { duration: 150 }
        }
    }
}
