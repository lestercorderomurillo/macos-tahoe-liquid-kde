// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
QQC.Slider {
    id: slider
    implicitHeight: 22
    hoverEnabled: true
    readonly property bool handleShown: enabled && (hovered || pressed || visualFocus)
    leftPadding: 0
    rightPadding: 0
    background: Rectangle {
        x: slider.leftPadding
        y: (slider.height - height) / 2
        width: slider.availableWidth
        height: 4
        radius: height / 2
        color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.16)
        Rectangle {
            width: slider.visualPosition * parent.width
            height: parent.height
            radius: parent.radius
            color: Kirigami.Theme.textColor
            opacity: slider.enabled ? 0.85 : 0.25
        }
    }
    handle: Item {
        id: thumb
        objectName: "glassSliderHandle"
        x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
        y: (slider.height - height) / 2
        // Keep pointer mapping fixed while the visual capsule appears.
        width: 18
        height: 14
        opacity: slider.handleShown ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 120 } }
        Rectangle {
            anchors.centerIn: parent
            width: parent.width
            height: parent.height
            radius: height / 2
            color: "#e6ffffff"
            border.width: 0.5
            border.color: "#33000000"
        }
    }
}
