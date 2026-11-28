// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

ShaderEffect {
    id: effect
    required property var lines
    property var source
    // Textured coverage comes directly from Qt's shaped, antialiased glyphs.
    // The color ramp is low-frequency, with no glyphs rasterized into it.
    property var ramp: ShaderEffectSource {
        hideSource: true
        smooth: true
        textureSize: Qt.size(Math.max(1, Math.ceil(effect.width)), Math.max(1, Math.ceil(effect.height)))
        sourceItem: InkColorRamp {
            parent: effect
            width: effect.width
            height: effect.height
            rows: effect.lines
        }
    }
    fragmentShader: "qrc:/org/kde/mac/tahoe/ink/inkgradient.frag.qsb"
}
