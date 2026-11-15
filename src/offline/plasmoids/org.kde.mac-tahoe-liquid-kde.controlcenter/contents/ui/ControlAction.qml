// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "ControlStyle.js" as Style
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
            implicitWidth: 36
            implicitHeight: implicitWidth
            radius: width / 2
            color: action.active ? "white" : "transparent"
            Kirigami.Icon {
                anchors.centerIn: parent
                width: action.compact ? Style.circleIcon : Style.actionIcon; height: width
                source: Style.symbol(action.symbol)
                color: action.active ? "#008aff" : Kirigami.Theme.textColor
                opacity: action.enabled ? 1 : 0.35
            }
        }
        ColumnLayout {
            visible: !action.compact
            spacing: 1
            Layout.fillWidth: true
            ControlLabel { text: action.text; font.pixelSize: Style.body; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
            ControlLabel { text: action.subtitle; visible: text.length > 0; font.pixelSize: Style.caption; opacity: 0.7; elide: Text.ElideRight; Layout.fillWidth: true }
        }
        Item { visible: action.compact; Layout.fillWidth: true }
    }
    QQC.ToolTip.visible: hovered && compact
    QQC.ToolTip.text: text
}
