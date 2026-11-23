// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.plasmoid

PanelWallpaper {
    id: sampler
    required property Item item
    required property color base
    property color fill: "transparent"
    property bool panelPalette: true
    property bool active: true
    readonly property GlassSettings settings: GlassSettings {}
    readonly property var panelSource: active && item?.Window.window
        ? sampler.sourceFor(item.Window.window, Plasmoid.containment) : null
    readonly property color foreground: {
        if (!panelSource) return base;
        const themeColor = panelPalette ? panelSource.baseForeground : base;
        if (!settings.dynamicTinting) return themeColor;
        panelSource.revision;
        return panelSource.foregroundFor(AdaptiveContrast.bounds(item), themeColor, fill);
    }
}
