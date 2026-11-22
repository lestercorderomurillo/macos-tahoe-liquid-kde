// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.networkmanagement as Network
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Controls
PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Network.ConnectionIcon { id: connection }
    Network.EnabledConnections { id: network }
    preferredRepresentation: fullRepresentation
    compactRepresentation: null
    fullRepresentation: Controls.PanelButton {
        wallpaperTint: Plasmoid.location === PlasmaCore.Types.TopEdge
        iconSize: 18.67
        symbol: network.wirelessEnabled ? (connection.connectionIcon.indexOf("wireless") >= 0 ? connection.connectionIcon : "network-wireless") : "network-wireless-offline"
        label: i18n("Wi-Fi")
        selected: popup.visible
        onClicked: popup.visible = !popup.visible
    }
    Connections { target: Plasmoid; function onActivated() { popup.visible = !popup.visible; } }
    Controls.ControlDialog {
        id: popup
        title: "mttkde-wifi"
        visible: false
        visualParent: root
        location: Plasmoid.location
        surfaces: menu.surfaces
        mainItem: Controls.StatusMenuPopup { id: menu; source: Qt.resolvedUrl("../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui/WifiView.qml"); width: implicitWidth; height: implicitHeight }
        onVisibleChanged: if (visible) { requestActivate(); menu.forceActiveFocus(); }
    }
}
