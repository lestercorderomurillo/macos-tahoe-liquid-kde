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

    font.weight: Font.Normal
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
        color: controlRoot.menuState === MenuDelegate.State.Rest
               ? "transparent"
               : Qt.rgba(0.5, 0.5, 0.5, controlRoot.menuState === MenuDelegate.State.Down ? 0.25 : 0.18)
    }

    contentItem: PC3.Label {
        text: controlRoot.Kirigami.MnemonicData.richTextLabel
        textFormat: Text.StyledText
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        color: Kirigami.Theme.textColor
        font.weight: controlRoot.font.weight
    }
}
