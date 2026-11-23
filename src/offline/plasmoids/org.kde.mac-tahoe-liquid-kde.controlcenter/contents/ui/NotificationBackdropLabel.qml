// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.kirigami as Kirigami

ControlLabel {
    id: label
    baseForeground: Kirigami.Theme.textColor
    property bool floating: false
    property color backdropColor: "transparent"
    color: {
        const window = label.Window.window;
        const base = Kirigami.Theme.textColor;
        return window && typeof window.foregroundFor === "function" ? window.foregroundFor(label, base) : base;
    }
    font.family: "SF Pro Display"; font.pixelSize: 13
}
