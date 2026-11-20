// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls as QQC
import "ControlStyle.js" as Style
QQC.Label {
    id: label
    // Draw the small letterforms from their outlines on translucent controls.
    Binding on renderType {
        when: label.Window.window && typeof label.Window.window.foregroundFor === "function"
            && label.GraphicsInfo.api !== GraphicsInfo.Software
        value: Text.CurveRendering
    }
    Binding on color {
        when: !!label.Window.window && typeof label.Window.window.foregroundFor === "function"
        value: when ? label.Window.window.foregroundFor(label, label.palette.windowText) : label.palette.windowText
    }
    font.family: Style.family
    font.pixelSize: Style.body
    font.weight: Font.Normal
}
