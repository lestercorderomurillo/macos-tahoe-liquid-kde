// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore

Text {
    id: label
    property string sourceText: ""
    property bool clockOverlay: false
    readonly property bool letterInk: clockOverlay && ink.active && ink.settings.dynamicTinting
        && ink.settings.contrastProfiles[contrastProfile]?.scope === "letter" && !!ink.panelSource && !!ink.material
    function glyphText() {
        const escape = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        const parts = ink.material.glyphs(sourceText, font);
        if (!parts.length) return escape(sourceText);
        let markup = "";
        for (const part of parts) {
            const p = label.mapToItem(null, part.point.x, part.point.y);
            const color = ink.forRect(Qt.rect(p.x - 0.25, p.y - 0.25, 0.5, 0.5), baseColor);
            markup += '<font color="' + color.toString() + '">' + escape(part.text) + '</font>';
        }
        return markup;
    }
    property string contrastProfile: ""
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
        profileId: label.contrastProfile
        surface: label.glass ?? label
        material: label.glass?.contrastMaterial ?? null
        base: label.baseColor
        panelPalette: false
        active: label.visible && (label.inPanel || !!label.glass)
        fill: label.glass ? Qt.rgba(label.glass.tint.r, label.glass.tint.g,
            label.glass.tint.b, label.glass.tintAlpha) : "transparent"
    }
    color: ink.foreground
}
