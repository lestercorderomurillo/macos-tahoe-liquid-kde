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
    preferredRepresentation: compactRepresentation
    compactRepresentation: Controls.PanelButton {
        symbol: network.wirelessEnabled ? (connection.connectionIcon.indexOf("wireless") >= 0 ? connection.connectionIcon : "network-wireless") : "network-wireless-offline"
        label: i18n("Wi-Fi")
        selected: root.expanded
        onClicked: root.expanded = !root.expanded
    }
    fullRepresentation: Controls.WifiView {}
}
