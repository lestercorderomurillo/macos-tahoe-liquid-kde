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

    font.weight: horizontalBar ? Font.Medium : Font.Normal
    readonly property bool lightText: Kirigami.ColorUtils.brightnessForColor(Kirigami.Theme.textColor)
                                      === Kirigami.ColorUtils.Light
    readonly property color foregroundColor: Qt.tint(Kirigami.Theme.textColor, lightText ? "#66ffffff" : "#66000000")

    property bool horizontalBar: true
    property bool goldenGate: false
    readonly property real titlePadding: horizontalBar ? (goldenGate ? 9.1 : 9.6) : 3 * Kirigami.Units.smallSpacing
    property real lightCapsuleOpacityBoost: 0
    property bool menuIsOpen: false
    property bool hoverOpensMenu: true

    signal activated(bool navigationOnly)

    hoverEnabled: true

    onHoveredChanged: if (hoverOpensMenu && hovered && menuIsOpen) { activated(true); }
    onPressed: activated(false)

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
    leftPadding: titlePadding
    rightPadding: titlePadding
    leftInset: horizontalBar ? (goldenGate ? -4.8 : -5.33) : 0
    rightInset: leftInset

    Accessible.description: i18nc("@info:usagetip", "Open a menu")

    background: Rectangle {
        y: (controlRoot.height - height) / 2
        height: controlRoot.horizontalBar ? Math.min(controlRoot.height, 24) : controlRoot.height - 2 * Math.min(Kirigami.Units.smallSpacing, controlRoot.height / 4)
        radius: Math.min(width, height) / 2

        readonly property color tint: controlRoot.lightText ? "#ffffff" : "#e3e7ee"

        readonly property real baseOpacity: controlRoot.menuState === MenuDelegate.State.Down ? 0.25 : 0.18
        readonly property real fillOpacity: baseOpacity + (controlRoot.lightText ? 0 : controlRoot.lightCapsuleOpacityBoost)

        visible: controlRoot.menuState !== MenuDelegate.State.Rest
        color: Qt.rgba(tint.r, tint.g, tint.b, fillOpacity)
    }

    contentItem: PC3.Label {
        text: controlRoot.Kirigami.MnemonicData.richTextLabel
        textFormat: Text.StyledText
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        color: controlRoot.foregroundColor
        font.letterSpacing: controlRoot.horizontalBar ? -0.35 : 0
        font.weight: controlRoot.font.weight
    }
}
