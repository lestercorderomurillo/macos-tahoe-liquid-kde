// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.plasmoid

PanelWallpaper {
    id: sampler
    required property Item item
    required property color base
    property color panelInk: base
    property bool active: true
    readonly property GlassSettings settings: GlassSettings {}
    readonly property int screenNumber: active ? Plasmoid.containment?.screen ?? -1 : -1
    watching: screenNumber >= 0 && settings.dynamicTinting && !!item?.Window.window

    readonly property color foreground: {
        if (!watching) return base
        sampler.revision
        // Follow the applet and its panel layout when delegates move or resize.
        let x = item.width / 2
        let y = item.height / 2
        for (let parentItem = item; parentItem; parentItem = parentItem.parent) {
            x += parentItem.x
            y += parentItem.y
        }
        const window = item.Window.window
        window.screen
        window.x
        window.y
        window.width
        window.height
        return foregroundAt(item, screenNumber, Qt.point(x, y), base, panelInk)
    }
}
