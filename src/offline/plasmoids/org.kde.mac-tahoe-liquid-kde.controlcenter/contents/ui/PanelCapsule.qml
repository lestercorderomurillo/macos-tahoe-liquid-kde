// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.kirigami as Kirigami

Rectangle {
    property bool pressed: false
    // Extra width on each side, for text items such as the clock.
    property real horizontalPadding: 0
    readonly property bool lightText: Kirigami.ColorUtils.brightnessForColor(Kirigami.Theme.textColor) === Kirigami.ColorUtils.Light
    anchors.centerIn: parent
    width: parent ? parent.width + 2 * horizontalPadding : 0
    height: parent ? Math.min(parent.height, 24) : 0
    radius: Math.min(width, height) / 2
    color: lightText ? "white" : "#e3e7ee"
    opacity: pressed ? 0.25 : 0.18
}
