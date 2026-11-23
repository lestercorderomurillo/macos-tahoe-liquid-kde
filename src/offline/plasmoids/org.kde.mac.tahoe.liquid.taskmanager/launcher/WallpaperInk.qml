// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.plasmoid

PanelWallpaper {
    id: sampler
    required property Item item
    required property color base
    property bool active: true
    readonly property GlassSettings settings: GlassSettings {}
    readonly property var panelSource: active && item?.Window.window
        ? sampler.sourceFor(item.Window.window, Plasmoid.containment) : null
    readonly property color foreground: !panelSource ? base
        : settings.dynamicTinting ? panelSource.foreground : panelSource.baseForeground
}
