// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.mac.tahoe.launcher as NativeGlass
import "ControlStyle.js" as Style
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.ksvg as KSvg
QQC.Pane {
    id: tile
    NativeGlass.GlassSettings { id: glassSettings; component: "control-center" }
    font.family: Style.family
    font.pixelSize: Style.body
    property real cornerRadius: Math.min(width, height) / 2
    readonly property bool lightMode: Kirigami.Theme.textColor.r * 0.2126 + Kirigami.Theme.textColor.g * 0.7152 + Kirigami.Theme.textColor.b * 0.0722 < 0.5
    readonly property bool goldenGate: material.hasElement("hint-clear-surface")
    KSvg.Svg { id: material; imagePath: "dialogs/background" }
    padding: 14
    background: Item {
        // Leave the centre translucent for the existing Acrylic Glass backend.
        Rectangle {
            anchors.fill: parent
            radius: tile.cornerRadius
            color: tile.lightMode ? Qt.rgba(1, 1, 1, glassSettings.lightOpacity >= 0 ? glassSettings.lightOpacity : 0.18)
                                 : Qt.rgba(1, 1, 1, glassSettings.darkOpacity >= 0 ? glassSettings.darkOpacity : 0.12)
        }
        GlassRim { anchors.fill: parent; cornerRadius: tile.cornerRadius; lightMode: tile.lightMode }
    }
}
