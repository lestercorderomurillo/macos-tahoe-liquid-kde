// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.ksvg as KSvg
QQC.Pane {
    id: tile
    property real cornerRadius: Math.min(width, height) / 2
    readonly property bool lightMode: Kirigami.Theme.textColor.r * 0.2126 + Kirigami.Theme.textColor.g * 0.7152 + Kirigami.Theme.textColor.b * 0.0722 < 0.5
    readonly property bool goldenGate: material.hasElement("hint-clear-surface")
    KSvg.Svg { id: material; imagePath: "dialogs/background" }
    padding: 14
    background: Item {
        Rectangle {
            anchors.fill: parent
            radius: tile.cornerRadius
            visible: tile.goldenGate
            gradient: Gradient {
                GradientStop { position: 0; color: "#d9000000" }
                GradientStop { position: 0.55; color: "transparent" }
            }
        }
        Rectangle {
            anchors.fill: parent
            radius: tile.cornerRadius
            color: tile.lightMode ? Qt.rgba(1, 1, 1, tile.goldenGate ? 0.60 : 0.55)
                                 : tile.goldenGate ? Qt.rgba(1, 1, 1, 0.01) : Qt.rgba(0, 0, 0, 0.48)
            border.width: 1
            border.color: tile.lightMode ? "#50ffffff" : "#30ffffff"
        }
    }
}
