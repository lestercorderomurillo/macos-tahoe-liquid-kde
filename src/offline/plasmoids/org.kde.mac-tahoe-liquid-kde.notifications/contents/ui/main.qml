// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.mac.tahoe.launcher as Native
import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Controls
PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation
    compactRepresentation: null
    fullRepresentation: Controls.PanelButton {
        symbol: "notifications"
        label: i18n("Notifications")
        selected: popup.visible
        onClicked: popup.visible = !popup.visible
    }
    Connections { target: Plasmoid; function onActivated() { popup.visible = !popup.visible; } }
    PlasmaCore.Dialog {
        id: popup
        // Notification history uses the same component material as Control Center.
        title: "mttkde-control-center"
        visible: false
        visualParent: root
        location: Plasmoid.location
        type: PlasmaCore.Dialog.AppletPopup
        flags: Qt.WindowStaysOnTopHint
        backgroundHints: PlasmaCore.Dialog.NoBackground
        hideOnWindowDeactivate: true
        mainItem: Controls.ControlTile {
            id: tile
            width: 360; height: implicitHeight
            cornerRadius: 24
            focus: true
            Keys.onEscapePressed: popup.visible = false
            contentItem: Controls.NotificationsView {}
        }
        onVisibleChanged: if (visible) { requestActivate(); tile.forceActiveFocus(); }
    }
    Native.ControlGlass {
        window: popup
        surfaces: [{x:0, y:0, width:tile.width, height:tile.height, radius:tile.cornerRadius}]
    }
}
