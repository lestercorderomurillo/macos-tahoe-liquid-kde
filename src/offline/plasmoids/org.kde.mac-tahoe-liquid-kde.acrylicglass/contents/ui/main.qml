// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Controls

PlasmoidItem {
    id: root
    Controls.SettingsEntry {
        id: settingsEntry
        section: "acrylic_glass"
        widgetId: 0
        onLaunchFailed: commands.run("acrylic")
    }
    Plasmoid.hasConfigurationInterface: !settingsEntry.available
    Plasmoid.contextualActions: [settingsEntry]
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation
    compactRepresentation: null
    fullRepresentation: Controls.PanelButton {
        wallpaperTint: Plasmoid.location === PlasmaCore.Types.TopEdge
        symbol: Plasmoid.icon
        label: Plasmoid.title
        onClicked: settingsEntry.open()
    }
    Controls.ControlCommands { id: commands }
    Connections {
        target: Plasmoid
        function onActivated() { settingsEntry.open(); }
    }
}
