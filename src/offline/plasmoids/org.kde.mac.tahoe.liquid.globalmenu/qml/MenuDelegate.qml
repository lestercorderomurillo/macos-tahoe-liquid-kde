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
        id: capsule

        y: Math.min(Kirigami.Units.smallSpacing, controlRoot.height / 4)
        height: Math.max(0, controlRoot.height - 2 * y)
        radius: Math.min(width, height) / 2
        // Panel foreground can follow the wallpaper, so pair the capsule with the actual label color.
        readonly property bool lightText: Kirigami.ColorUtils.brightnessForColor(Kirigami.Theme.textColor)
                                          === Kirigami.ColorUtils.Light
        readonly property bool pressed: controlRoot.menuState === MenuDelegate.State.Down
        readonly property real fillOpacity: pressed ? 0.30 : 0.20
        readonly property real gradientOffset: lightText ? 0.08 : -0.08

        visible: controlRoot.menuState !== MenuDelegate.State.Rest
        border.width: 1
        border.color: overlay(pressed ? 0.65 : 0.50)
        gradient: Gradient {
            GradientStop {
                position: 0
                color: capsule.overlay(capsule.fillOpacity + capsule.gradientOffset)
            }
            GradientStop {
                position: 1
                color: capsule.overlay(capsule.fillOpacity - capsule.gradientOffset)
            }
        }

        // Source-over tint shifts the visible backdrop without flattening its colors.
        function overlay(alpha: real): color {
            const channel = lightText ? 1 : 0;
            return Qt.rgba(channel, channel, channel, alpha);
        }
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
