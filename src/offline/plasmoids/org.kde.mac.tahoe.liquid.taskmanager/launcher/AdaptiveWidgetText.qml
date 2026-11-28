// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore

Text {
    id: label
    property string sourceText: ""
    property bool clockOverlay: false
    readonly property var profile: ink.settings.contrastProfiles[contrastProfile]
    readonly property bool useRuns: ink.active && ink.settings.dynamicTinting && !!ink.panelSource && !!profile
        && (profile.scope === "letter" || (profile.scope === "line" && wrapMode !== Text.NoWrap))
        && (contrastProfile !== "widget.clock-glass-text" || clockOverlay)
        && sourceText.length > 0 && !/<[a-zA-Z][^>]*>/.test(sourceText)
    function glyphText() {
        return AdaptiveContrast.styledRuns(label, sourceText, profile, r => ink.forRect(r, baseColor));
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
