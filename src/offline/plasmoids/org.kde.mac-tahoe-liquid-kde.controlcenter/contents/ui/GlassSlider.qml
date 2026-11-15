// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
QQC.Slider {
    id: slider
    implicitHeight: 22
    leftPadding: 0
    rightPadding: 0
    background: Rectangle {
        x: slider.leftPadding
        y: (slider.height - height) / 2
        width: slider.availableWidth
        height: 7
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
    handle: Rectangle {
        x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
        y: (slider.height - height) / 2
        width: slider.pressed || slider.activeFocus ? 14 : 7
        height: width
        radius: width / 2
        color: Kirigami.Theme.textColor
        opacity: slider.enabled ? 0.9 : 0.25
        Behavior on width { NumberAnimation { duration: 100 } }
    }
}
