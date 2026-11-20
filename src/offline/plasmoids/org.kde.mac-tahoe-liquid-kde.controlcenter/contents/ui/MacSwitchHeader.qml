// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
// Title row of a macOS Tahoe module menu: bold name and a blue pill switch.
QQC.Switch {
    id: toggle
    readonly property bool lightMode: Kirigami.Theme.textColor.r * 0.2126 + Kirigami.Theme.textColor.g * 0.7152 + Kirigami.Theme.textColor.b * 0.0722 < 0.5
    Layout.fillWidth: true
    implicitHeight: 36
    leftPadding: 6; rightPadding: 6
    contentItem: ControlLabel { text: toggle.text; font.weight: Font.DemiBold; verticalAlignment: Text.AlignVCenter; rightPadding: 60 }
    indicator: Rectangle {
        x: toggle.width - width - toggle.rightPadding
        y: (toggle.height - height) / 2
        width: 50; height: 24; radius: 12
        color: toggle.checked ? "#008aff" : toggle.lightMode ? Qt.rgba(0,0,0,0.18) : Qt.rgba(1,1,1,0.22)
        opacity: toggle.enabled ? 1 : 0.4
        Rectangle {
            x: toggle.checked ? parent.width - width - 2 : 2; y: 2; width: 30; height: 20; radius: 10; color: "white"
            Behavior on x { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        }
    }
    background: Rectangle { radius: 8; color: Kirigami.Theme.textColor; opacity: toggle.activeFocus ? 0.10 : 0 }
}
