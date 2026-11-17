/*
    SPDX-FileCopyrightText: 2020 Carson Black <uhhadd@gmail.com>
    SPDX-License-Identifier: GPL-2.0-or-later
*/

import QtQuick
import QtQuick.Controls

import org.kde.plasma.components as PC3
import org.kde.kirigami as Kirigami

AbstractButton {
    id: controlRoot

    font.weight: Font.Bold
    property int originalFontWeight: Font.Normal
    readonly property bool lightText: Kirigami.ColorUtils.brightnessForColor(Kirigami.Theme.textColor)
                                      === Kirigami.ColorUtils.Light
    readonly property color foregroundColor: Qt.tint(Kirigami.Theme.textColor, lightText ? "#40ffffff" : "#40000000")

    property bool menuIsOpen: false
    property bool hoverOpensMenu: true

    signal activated()

    hoverEnabled: true

    onHoveredChanged: if (hoverOpensMenu && hovered && menuIsOpen) { activated(); }
    onPressed: activated()

    enum State {
        Rest,
        Hover,
        Down
    }

    property int menuState: {
        if (down) {
            return MenuDelegate.State.Down;
        } else if (hovered && !menuIsOpen) {
            return MenuDelegate.State.Hover;
        }
        return MenuDelegate.State.Rest;
    }

    Kirigami.MnemonicData.controlType: Kirigami.MnemonicData.SecondaryControl
    Kirigami.MnemonicData.label: text

    topPadding: Kirigami.Units.smallSpacing
    bottomPadding: Kirigami.Units.smallSpacing
    leftPadding: 3 * Kirigami.Units.smallSpacing
    rightPadding: 3 * Kirigami.Units.smallSpacing

    Accessible.description: i18nc("@info:usagetip", "Open a menu")

    background: Rectangle {
        y: Math.min(Kirigami.Units.smallSpacing, controlRoot.height / 4)
        height: Math.max(0, controlRoot.height - 2 * y)
        radius: Math.min(width, height) / 2

        readonly property color tint: controlRoot.lightText ? "#ffffff" : "#e3e7ee"

        visible: controlRoot.menuState !== MenuDelegate.State.Rest
        color: Qt.rgba(tint.r, tint.g, tint.b, controlRoot.menuState === MenuDelegate.State.Down ? 0.25 : 0.18)
    }

    contentItem: Item {
        implicitWidth: originalLabel.implicitWidth
        implicitHeight: originalLabel.implicitHeight

        PC3.Label {
            id: label

            // The heavier text can use existing padding without moving any menu buttons.
            width: Math.min(parent.width + controlRoot.rightPadding, Math.max(parent.width, implicitWidth))
            height: parent.height
            text: controlRoot.Kirigami.MnemonicData.richTextLabel
            textFormat: Text.StyledText
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            color: controlRoot.foregroundColor
            font.weight: controlRoot.font.weight
        }

        PC3.Label {
            id: originalLabel
            visible: false
            text: label.text
            textFormat: label.textFormat
            font.weight: controlRoot.originalFontWeight
        }
    }
}
