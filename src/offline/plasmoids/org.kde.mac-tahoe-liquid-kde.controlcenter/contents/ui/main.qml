// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "NotificationContrast.js" as Contrast
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.mac.tahoe.launcher as Native
PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    StatusTrayStyle { panelItem: root }
    preferredRepresentation: fullRepresentation
    compactRepresentation: null
    fullRepresentation: PanelButton {
        symbol: Qt.resolvedUrl("controlcenter.svg")
        label: i18n("Control Center")
        selected: popup.visible
        onClicked: popup.visible = !popup.visible
    }
    toolTipMainText: popup.visible ? "" : i18n("Control Center")
    toolTipSubText: ""
    Connections { target: Plasmoid; function onActivated() { popup.visible = !popup.visible; } }
    PlasmaCore.Dialog {
        id: popup
        title: "mttkde-control-center"
        function foregroundFor(item: Item, base: color): color {
            glass.backdropRevision; // Re-evaluate when the compositor samples a new frame.
            const point = item.mapToItem(popup.contentItem, item.width / 2, item.height / 2);
            let tile = item;
            while (tile && tile.fillColor === undefined) tile = tile.parent;
            return Contrast.foreground(base, glass.backdropAt(point), tile ? tile.fillColor : Qt.rgba(0, 0, 0, 0));
        }
        visible: false
        visualParent: root
        location: Plasmoid.location
        type: PlasmaCore.Dialog.AppletPopup
        flags: Qt.WindowStaysOnTopHint
        backgroundHints: PlasmaCore.Dialog.NoBackground
        hideOnWindowDeactivate: true
        mainItem: ControlView { id: controls; preferences: Plasmoid.configuration; width: implicitWidth; height: implicitHeight; onCloseRequested: popup.visible = false }
        onVisibleChanged: { if (visible) { requestActivate(); controls.forceActiveFocus(); } else controls.section = ""; }
    }
    Native.ControlGlass { id: glass; window: popup; surfaces: controls.surfaces }
}
