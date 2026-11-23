// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore

Text {
    id: label
    property color baseColor: "black"
    readonly property Item glass: {
        for (let parent = label.parent; parent; parent = parent.parent) {
            for (const child of parent.children) {
                if (child.objectName === "mttkde-widget-material") return child;
            }
            if (parent.Window.window?.contentItem === parent) break;
        }
        return null;
    }
    readonly property bool inPanel: Plasmoid.location === PlasmaCore.Types.TopEdge
    WallpaperInk {
        id: ink
        item: label
        base: label.baseColor
        panelPalette: false
        active: label.inPanel || (!!label.glass && !label.glass.solidMode)
        fill: label.glass ? Qt.rgba(label.glass.tint.r, label.glass.tint.g,
            label.glass.tint.b, label.glass.tintAlpha) : "transparent"
    }
    color: ink.foreground
}
