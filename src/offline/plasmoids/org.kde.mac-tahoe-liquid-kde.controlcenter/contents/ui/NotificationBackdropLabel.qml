// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "NotificationContrast.js" as Contrast
import QtQuick.Effects
import org.kde.kirigami as Kirigami

ControlLabel {
    id: label
    property bool floating: false
    property color backdropColor: "transparent"
    color: floating && backdropColor.a > 0
        ? Contrast.foreground(Kirigami.Theme.textColor, backdropColor, Qt.rgba(0,0,0,0))
        : floating ? "white" : Kirigami.Theme.textColor
    font.family: "SF Pro Display"; font.pixelSize: 13
    // Qt's software scenegraph cannot render MultiEffect shader layers.
    style: floating && GraphicsInfo.api === GraphicsInfo.Software ? Text.Raised : Text.Normal
    styleColor: Contrast.luminance(color) > 0.5 ? "#99000000" : "#99ffffff"
    layer.enabled: floating && GraphicsInfo.api !== GraphicsInfo.Software
        && GraphicsInfo.api !== GraphicsInfo.Unknown
    layer.effect: MultiEffect {
        shadowEnabled: true
        shadowBlur: 0.35; blurMax: 12
        shadowColor: Contrast.luminance(label.color) > 0.5 ? "#e0000000" : "#a0ffffff"; shadowScale: 1.0
        shadowVerticalOffset: 1
        autoPaddingEnabled: true
    }
}
