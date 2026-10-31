// SPDX-License-Identifier: GPL-2.0-or-later
import QtQuick
import org.kde.plasma.core as PlasmaCore
import org.kde.mac.tahoe.launcher as NativeLauncher

Item {
    id: root
    width: 600
    height: 300
    property real minimumWidth: reference.width
    property int caseIndex: 0
    readonly property var edges: [PlasmaCore.Types.BottomEdge, PlasmaCore.Types.TopEdge,
                                 PlasmaCore.Types.LeftEdge, PlasmaCore.Types.RightEdge]
    // Reuse the same items throughout: growing, shrinking, fractional cell
    // extents, rectangular cells and orientation changes must rebind correctly.
    readonly property var sizes: [16, 22, 24, 31.5, 32, 47.5, 48, 64, 96, 128,
                                 96, 64, 48, 47.5, 32, 31.5, 24, 22, 16]
    readonly property var aspects: [1, 0.75, 1.5]
    readonly property int panelCases: edges.length * sizes.length * aspects.length
    ReferenceTaskIcon { id: reference; width: 64; height: 64 }
    NativeLauncher.DockIcon { id: custom; width: reference.width; height: reference.height; source: "folder" }

    NativeLauncher.DockIcon {
        id: trash
        width: reference.width; height: reference.height
        location: custom.location
        inPanel: custom.inPanel
        normalizeTrashArtwork: true
        source: root.caseIndex % 3 === 0 ? "user-trash"
            : root.caseIndex % 3 === 1 ? "user-trash-full" : "folder"
    }

    function compareTrashArtwork() {
        const corrected = custom.inPanel && trash.source !== "folder"
            && Math.min(custom.iconItem.width, custom.iconItem.height) > 24;
        const factor = corrected ? 56 / 53 : 1;
        root.compare(trash.iconItem.width, custom.iconItem.width * factor);
        root.compare(trash.iconItem.height, custom.iconItem.height * factor);
        const base = custom.iconItem.mapToItem(custom, custom.iconItem.width / 2, custom.iconItem.height / 2);
        const actual = trash.iconItem.mapToItem(trash, trash.iconItem.width / 2, trash.iconItem.height / 2);
        const size = Math.min(custom.iconItem.width, custom.iconItem.height);
        root.compare(actual.x, base.x);
        if (corrected) {
            // Compare the real SVG body bounds (y=6..59) with app tiles
            // (y=4..60), including their asymmetric internal padding.
            const fitted = size * factor;
            root.compare(actual.y + (6 / 64 - 0.5) * fitted, base.y - size * 28 / 64);
            root.compare(actual.y + (59 / 64 - 0.5) * fitted, base.y + size * 28 / 64);
        } else {
            root.compare(actual.y, base.y);
        }
    }

    function compare(a, b) {
        if (!isFinite(a) || !isFinite(b) || Math.abs(a - b) > 0.01) {
            throw new Error("Dock geometry case " + caseIndex + ": " + a + " != " + b);
        }
    }
    function prepare() {
        if (caseIndex < panelCases) {
            const size = sizes[caseIndex % sizes.length];
            const group = Math.floor(caseIndex / sizes.length);
            const edge = edges[Math.floor(group / aspects.length)];
            const vertical = edge === PlasmaCore.Types.LeftEdge || edge === PlasmaCore.Types.RightEdge;
            const aspect = aspects[group % aspects.length];
            reference.width = vertical ? size : size * aspect;
            reference.height = vertical ? size * aspect : size;
            reference.location = edge;
            custom.location = edge;
            // Cell positions can be fractional after panel resizing/reordering.
            custom.x = caseIndex % 2 ? 200.5 : 200;
            custom.y = caseIndex % 3 ? 0.25 : 0;
        } else {
            custom.inPanel = false;
            reference.width = 64;
            reference.height = 48;
        }
    }
    Component.onCompleted: prepare()
    Timer {
        interval: 1
        running: true
        repeat: true
        onTriggered: {
            try {
                root.compareTrashArtwork();
                const a = custom.iconItem.mapToItem(custom, 0, 0);
                const b = reference.iconItem.mapToItem(reference, 0, 0);
                if (root.caseIndex < root.panelCases) {
                    root.compare(a.x, b.x);
                    root.compare(a.y, b.y);
                    root.compare(custom.iconItem.width, reference.iconItem.width);
                    root.compare(custom.iconItem.height, reference.iconItem.height);
                } else {
                    root.compare(custom.iconItem.width, 48);
                    root.compare(custom.iconItem.height, 48);
                    root.compare(a.x, 8);
                    root.compare(a.y, 0);
                    console.info("DOCK_ALIGNMENT_OK:", root.panelCases, "resize/edge/aspect cases and desktop geometry");
                    stop();
                    Qt.exit(0);
                    return;
                }
                root.caseIndex++;
                root.prepare();
            } catch (error) {
                console.error(error);
                stop();
                Qt.exit(1);
            }
        }
    }
}
