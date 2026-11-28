// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.plasmoid

PanelWallpaper {
    id: sampler
    required property Item item
    required property color base
    property string profileId: "panel.symbol"
    property MaterialSample material: null
    property color groupReference: base
    property Item surface: item
    property Item componentSurface: surface
    property color fill: "transparent"
    property bool panelPalette: true
    property bool active: true
    readonly property GlassSettings settings: GlassSettings {}
    readonly property var panelSource: active && item?.Window.window
        ? sampler.sourceFor(item.Window.window, Plasmoid.containment) : null
    function forRect(rect, reference, run = -1) {
        if (!panelSource) return base;
        panelSource.revision;
        if (material) material.revision;
        return panelSource.foregroundFor(rect, base, fill, settings.contrastProfiles[profileId], material, reference, item, run);
    }
    readonly property color foreground: {
        if (!panelSource) return base;
        const themeColor = panelPalette ? panelSource.baseForeground : base;
        if (!settings.dynamicTinting) return themeColor;
        panelSource.revision;
        const profile = settings.contrastProfiles[profileId];
        if (!profile) return themeColor;
        const group = profile.scope === "component" ? componentSurface : profile.scope === "bubble" ? surface : null;
        const rect = group ? AdaptiveContrast.surfaceBounds(group) : AdaptiveContrast.bounds(item);
        if (material) material.revision;
        return panelSource.foregroundFor(rect, themeColor, fill, profile, material, group && !panelPalette ? groupReference : themeColor, item);
    }
}
