// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Controls

PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation
    compactRepresentation: null
    fullRepresentation: Controls.PanelButton {
        wallpaperTint: Plasmoid.location === PlasmaCore.Types.TopEdge
        symbol: Plasmoid.icon
        label: Plasmoid.title
        onClicked: commands.run("acrylic")
    }
    Controls.ControlCommands { id: commands }
    Connections {
        target: Plasmoid
        function onActivated() { commands.run("acrylic"); }
    }
}
