// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
QQC.AbstractButton {
    id: action
    property string symbol
    property string subtitle
    property bool active: false
    property bool compact: false
    Accessible.name: text
    background: Rectangle { radius: height / 2; color: "white"; opacity: action.down ? 0.2 : action.hovered || action.activeFocus ? 0.1 : 0 }
    contentItem: RowLayout {
        spacing: 8
        Item { visible: action.compact; Layout.fillWidth: true }
        Rectangle {
            implicitWidth: action.compact ? 36 : 34
            implicitHeight: implicitWidth
            radius: width / 2
            color: action.active ? "white" : "transparent"
            Kirigami.Icon {
                anchors.centerIn: parent
                width: action.compact ? 26 : 21; height: width
                source: action.symbol
                color: action.active ? "#008aff" : Kirigami.Theme.textColor
                opacity: action.enabled ? 1 : 0.35
            }
        }
        ColumnLayout {
            visible: !action.compact
            spacing: 1
            Layout.fillWidth: true
            QQC.Label { text: action.text; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
            QQC.Label { text: action.subtitle; visible: text.length > 0; font.pixelSize: 10; opacity: 0.7; elide: Text.ElideRight; Layout.fillWidth: true }
        }
        Item { visible: action.compact; Layout.fillWidth: true }
    }
    QQC.ToolTip.visible: hovered && compact
    QQC.ToolTip.text: text
}
