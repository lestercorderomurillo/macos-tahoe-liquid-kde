// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.kirigami as Kirigami

Rectangle {
    property bool pressed: false
    readonly property bool lightText: Kirigami.ColorUtils.brightnessForColor(Kirigami.Theme.textColor) === Kirigami.ColorUtils.Light
    anchors.centerIn: parent
    width: parent ? parent.width : 0
    height: parent ? Math.min(parent.height, 24) : 0
    radius: Math.min(width, height) / 2
    color: lightText ? "white" : "#e3e7ee"
    opacity: pressed ? 0.25 : 0.18
}
