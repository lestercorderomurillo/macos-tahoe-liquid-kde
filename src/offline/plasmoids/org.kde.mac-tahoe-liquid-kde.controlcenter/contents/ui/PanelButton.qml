// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
Item {
    id: button
    property string symbol
    property string label
    property bool selected: false
    signal clicked()
    implicitWidth: Kirigami.Units.iconSizes.smallMedium + Kirigami.Units.smallSpacing * 2
    implicitHeight: implicitWidth
    Layout.minimumWidth: implicitWidth
    Layout.fillHeight: true
    activeFocusOnTab: true
    Accessible.name: label
    Accessible.role: Accessible.Button
    Accessible.onPressAction: clicked()
    Keys.onSpacePressed: clicked()
    Keys.onReturnPressed: clicked()
    Rectangle {
        anchors.fill: parent
        radius: Kirigami.Units.smallSpacing
        color: Kirigami.Theme.textColor
        opacity: pointer.pressed ? 0.16 : pointer.containsMouse || button.selected || button.activeFocus ? 0.09 : 0
    }
    Kirigami.Icon {
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height, Kirigami.Units.iconSizes.smallMedium)
        height: width
        source: button.symbol
        color: Kirigami.Theme.textColor
    }
    MouseArea {
        id: pointer
        anchors.fill: parent
        hoverEnabled: true
        onClicked: button.clicked()
    }
}
