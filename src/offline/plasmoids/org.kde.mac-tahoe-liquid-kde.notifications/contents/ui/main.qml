// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Controls
PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: compactRepresentation
    compactRepresentation: Controls.PanelButton {
        symbol: "notifications"
        label: i18n("Notifications")
        selected: root.expanded
        onClicked: root.expanded = !root.expanded
    }
    fullRepresentation: Controls.NotificationsView {}
}
