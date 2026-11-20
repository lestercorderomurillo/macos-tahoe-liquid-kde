// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import "ControlStyle.js" as Style

QQC.AbstractButton {
    id: row
    property string symbol
    property bool selected: false
    property bool secured: false
    property bool busy: false
    property bool disclosure: false
    property bool opened: false
    property string detail
    readonly property bool lightMode: Kirigami.Theme.textColor.r * 0.2126 + Kirigami.Theme.textColor.g * 0.7152 + Kirigami.Theme.textColor.b * 0.0722 < 0.5
    implicitHeight: 32
    implicitWidth: 270
    leftPadding: 6; rightPadding: 6; topPadding: 3; bottomPadding: 3
    hoverEnabled: true
    Accessible.name: text
    background: Rectangle {
        radius: 8
        color: row.lightMode ? Qt.rgba(0, 0, 0, 0.08) : Qt.rgba(1, 1, 1, 0.12)
        visible: row.down || row.hovered || row.activeFocus
    }
    contentItem: RowLayout {
        spacing: 8
        Rectangle {
            visible: row.symbol.length > 0
            implicitWidth: 26; implicitHeight: 26; radius: 13
            // macOS Tahoe: the active item is a white disc with a blue symbol.
            color: row.selected ? (row.lightMode ? "#008aff" : "white") : row.lightMode ? Qt.rgba(0, 0, 0, 0.10) : Qt.rgba(1, 1, 1, 0.22)
            Kirigami.Icon {
                anchors.centerIn: parent
                width: 16; height: 16
                roundToIconSize: false
                source: Style.symbol(row.symbol)
                isMask: true
                color: row.selected ? (row.lightMode ? "white" : "#008aff") : caption.color
                visible: !row.busy
            }
            QQC.BusyIndicator { anchors.centerIn: parent; width: 22; height: 22; running: row.busy; visible: running }
        }
        ControlLabel {
            id: caption
            text: row.text
            textFormat: Text.PlainText
            elide: Text.ElideRight
            Layout.fillWidth: true; Layout.minimumWidth: 0
        }
        ControlLabel { visible: row.detail.length > 0; text: row.detail; opacity: 0.65; font.pixelSize: 11 }
        Kirigami.Icon { visible: row.secured; source: Style.symbol("mac-menu-lock"); isMask: true; color: caption.color; implicitWidth: 12; implicitHeight: 14; opacity: 0.65 }
        Kirigami.Icon { visible: row.disclosure; source: Style.symbol("mac-menu-chevron"); rotation: row.opened ? 0 : -90; isMask: true; color: caption.color; implicitWidth: 12; implicitHeight: 12; opacity: 0.65 }
    }
}
