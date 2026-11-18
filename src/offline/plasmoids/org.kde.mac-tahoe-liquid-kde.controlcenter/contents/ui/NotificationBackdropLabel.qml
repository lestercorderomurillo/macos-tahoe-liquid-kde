// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Effects
import org.kde.kirigami as Kirigami

ControlLabel {
    property bool floating: false
    color: floating ? "white" : Kirigami.Theme.textColor
    font.family: "SF Pro Display"; font.pixelSize: 13
    // Qt's software scenegraph cannot render MultiEffect shader layers.
    style: floating && GraphicsInfo.api === GraphicsInfo.Software ? Text.Raised : Text.Normal
    styleColor: "#99000000"
    layer.enabled: floating && GraphicsInfo.api !== GraphicsInfo.Software
        && GraphicsInfo.api !== GraphicsInfo.Unknown
    layer.effect: MultiEffect {
        shadowEnabled: true
        shadowBlur: 0.35; blurMax: 12
        shadowColor: "#e0000000"; shadowScale: 1.0
        shadowVerticalOffset: 1
        autoPaddingEnabled: true
    }
}
