// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "ControlStyle.js" as Style
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
// Fills its whole tile so the hover/press wash covers the tile edge to edge.
// Wide tiles: a 36 px symbol disc concentric with the 63 px capsule end, then
// the labels. Compact (round) tiles: the symbol is centred and, when active,
// the whole circle turns white as in macOS Tahoe.
QQC.AbstractButton {
    id: action
    property string symbol
    property string subtitle
    property bool active: false
    property bool compact: false
    property bool iconDisc: false
    property color activeSymbolColor: "#008aff"
    // macOS: the symbol disc toggles the service, the rest of the tile opens its module.
    property bool discToggles: false
    // Modules with a detail menu show a translucent chevron while hovered.
    property bool disclosure: false
    // A switched-off service (AirDrop Off): darker disc and dimmed symbol.
    property bool serviceOff: false
    signal discClicked()
    property real symbolSize: compact ? Style.circleIcon : Style.actionIcon
    readonly property real discSize: 36
    Accessible.name: text
    hoverEnabled: true
    padding: 0
    leftPadding: compact ? 0 : Math.round((height - discSize) / 2)
    rightPadding: compact ? 0 : 6
    background: Rectangle {
        radius: Math.min(width, height) / 2
        color: "white"
        opacity: action.compact && action.active ? (action.down ? 0.85 : 1)
               : action.down ? 0.2 : action.hovered || action.visualFocus ? 0.1 : 0
    }
    contentItem: Item {
        implicitHeight: action.compact ? action.symbolSize : action.discSize
        Rectangle {
            id: disc
            visible: !action.compact
            width: action.discSize; height: width
            anchors.verticalCenter: parent.verticalCenter
            radius: width / 2
            color: action.active ? "white" : action.serviceOff ? Qt.rgba(1,1,1,0.12) : action.iconDisc || action.discToggles ? Qt.rgba(1,1,1,0.22) : "transparent"
            MouseArea {
                anchors.fill: parent
                enabled: action.discToggles && action.enabled
                cursorShape: Qt.PointingHandCursor
                onClicked: action.discClicked()
            }
        }
        Kirigami.Icon {
            anchors.centerIn: action.compact ? parent : disc
            width: action.symbolSize; height: width
            roundToIconSize: false
            source: Style.symbol(action.symbol)
            color: action.active ? action.activeSymbolColor : Style.foreground(this, Window.window, Kirigami.Theme.textColor)
            // An inactive service symbol (AirDrop Off) is dimmed, as on macOS.
            opacity: !action.enabled ? 0.35 : action.serviceOff ? 0.5 : 1
        }
        ColumnLayout {
            visible: !action.compact
            x: disc.width + 7
            width: parent.width - x
            anchors.verticalCenter: parent.verticalCenter
            spacing: 0
            ControlLabel { text: action.text; font.pixelSize: Style.tileTitle; font.weight: Font.DemiBold; textFormat: Text.PlainText; wrapMode: Text.WordWrap; // Shrink a single long word (fr "Concentration") instead of breaking it.
                fontSizeMode: action.text.indexOf(" ") < 0 ? Text.HorizontalFit : Text.FixedSize; minimumPixelSize: 10; maximumLineCount: 2; elide: Text.ElideRight; lineHeight: 15; lineHeightMode: Text.FixedHeight; Layout.fillWidth: true; Layout.minimumWidth: 0 }
            ControlLabel { text: action.subtitle; visible: text.length > 0; font.pixelSize: Style.caption; opacity: 0.7; textFormat: Text.PlainText; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; lineHeight: 14; lineHeightMode: Text.FixedHeight; Layout.fillWidth: true; Layout.minimumWidth: 0 }
        }
    }
    Kirigami.Icon {
        objectName: "disclosureChevron"
        visible: action.disclosure && !action.compact
        width: 20; height: 20
        roundToIconSize: false
        anchors.verticalCenter: parent.verticalCenter
        anchors.right: parent.right; anchors.rightMargin: 8
        source: Style.symbol("mac-chevron-right")
        color: Style.foreground(this, Window.window, Kirigami.Theme.textColor)
        opacity: action.hovered || action.visualFocus ? 0.6 : 0
        Behavior on opacity { NumberAnimation { duration: 120 } }
    }
    QQC.ToolTip.visible: hovered && compact
    QQC.ToolTip.text: text
}
