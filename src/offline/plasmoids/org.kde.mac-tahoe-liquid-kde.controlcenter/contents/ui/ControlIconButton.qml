// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
QQC.ToolButton {
    id: button
    icon.color: "white"
    display: QQC.AbstractButton.IconOnly
    Accessible.name: text
    // The desktop style paints an icon inside its native ToolButton background.
    // Draw only interaction feedback there so the symbolic glyph has one edge.
    background: Rectangle {
        radius: height / 2
        color: button.down ? "#33ffffff" : button.hovered || button.visualFocus ? "#1affffff" : "transparent"
        border.width: button.visualFocus ? 1 : 0
        border.color: "white"
    }
    contentItem: Item {
        implicitWidth: button.icon.width > 0 ? button.icon.width : 20
        implicitHeight: button.icon.height > 0 ? button.icon.height : 20
        Kirigami.Icon {
            objectName: "controlIcon"
            anchors.centerIn: parent
            width: parent.implicitWidth
            height: parent.implicitHeight
            isMask: true
            Kirigami.Theme.inherit: false
            Kirigami.Theme.colorGroup: Kirigami.Theme.Active
            source: button.icon.source.toString().length ? button.icon.source : button.icon.name
            color: button.icon.color
            opacity: button.enabled ? 1 : 0.55
        }
    }
}
