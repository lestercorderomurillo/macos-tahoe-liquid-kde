// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.mac.tahoe.launcher as NativeGlass
import "ControlStyle.js" as Style
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.ksvg as KSvg
QQC.Pane {
    id: tile
    NativeGlass.GlassSettings { id: glassSettings; component: tile.materialComponent }
    font.family: Style.family
    font.pixelSize: Style.body
    property string materialComponent: "control-center"
    property real lightFallback: 0.18
    property real darkFallback: 0.12
    property real rimWidth: 1.25
    property bool doubleRim: false
    property color darkTint: "white"
    property real cornerRadius: Math.min(width, height) / 2
    readonly property bool lightMode: Kirigami.Theme.textColor.r * 0.2126 + Kirigami.Theme.textColor.g * 0.7152 + Kirigami.Theme.textColor.b * 0.0722 < 0.5
    readonly property bool goldenGate: material.hasElement("hint-clear-surface")
    KSvg.Svg { id: material; imagePath: "dialogs/background" }
    readonly property color fillColor: backgroundTint.color
    padding: 14
    background: Item {
        // Leave the centre translucent for the existing Acrylic Glass backend.
        Rectangle {
            id: backgroundTint
            anchors.fill: parent
            radius: tile.cornerRadius
            border.width: tile.doubleRim ? 0.75 : 0
            border.color: Qt.rgba(0, 0, 0, 0.18)
            color: tile.lightMode ? Qt.rgba(1, 1, 1, glassSettings.lightOpacity >= 0 ? glassSettings.lightOpacity : tile.lightFallback)
                                 : Qt.rgba(tile.darkTint.r, tile.darkTint.g, tile.darkTint.b, glassSettings.darkOpacity >= 0 ? glassSettings.darkOpacity : tile.darkFallback)
        }
        Rectangle {
            visible: tile.doubleRim
            anchors.fill: parent; anchors.margins: 0.75
            radius: Math.max(0, tile.cornerRadius - 0.75)
            color: "transparent"
            border.width: 0.75
            border.color: Qt.rgba(1, 1, 1, 0.22)
        }
        GlassRim { visible: !tile.doubleRim; anchors.fill: parent; cornerRadius: tile.cornerRadius; lineWidth: tile.rimWidth; lightMode: tile.lightMode }
    }
}
