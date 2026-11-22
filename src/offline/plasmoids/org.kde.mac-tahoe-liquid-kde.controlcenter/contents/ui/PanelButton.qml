// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "ControlStyle.js" as Style
import QtQuick.Layouts
import org.kde.mac.tahoe.launcher as Native
import org.kde.kirigami as Kirigami
Item {
    id: button
    property string symbol
    property string label
    property bool wallpaperTint: false
    property bool selected: false
    signal clicked()
    property real iconSize: 16
    implicitWidth: 30
    implicitHeight: implicitWidth
    Layout.minimumWidth: implicitWidth
    Layout.fillHeight: true
    activeFocusOnTab: true
    Accessible.name: label
    Accessible.role: Accessible.Button
    Accessible.onPressAction: clicked()
    Keys.onSpacePressed: clicked()
    Keys.onReturnPressed: clicked()
    PanelCapsule {
        pressed: pointer.pressed
        visible: pressed || pointer.containsMouse || button.selected || button.activeFocus
    }
    Native.WallpaperInk {
        id: ink
        item: button
        base: Kirigami.Theme.textColor
        active: button.wallpaperTint
    }
    Kirigami.Icon {
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height, button.iconSize)
        roundToIconSize: false
        height: width
        source: Style.symbol(button.symbol)
        isMask: true
        color: ink.foreground
    }
    MouseArea {
        id: pointer
        anchors.fill: parent
        hoverEnabled: true
        onClicked: button.clicked()
    }
}
