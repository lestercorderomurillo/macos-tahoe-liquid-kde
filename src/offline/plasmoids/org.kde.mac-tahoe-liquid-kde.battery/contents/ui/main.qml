// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.private.battery as Power
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Controls
PlasmoidItem {
    id: root
    Controls.SettingsEntry { id: settingsEntry; widgetId: Plasmoid.id }
    Plasmoid.hasConfigurationInterface: !settingsEntry.available
    Plasmoid.contextualActions: [settingsEntry]
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Power.BatteryControlModel { id: power }
    preferredRepresentation: fullRepresentation
    compactRepresentation: null
    fullRepresentation: Controls.PanelButton {
        wallpaperTint: Plasmoid.location === PlasmaCore.Types.TopEdge
        symbol: !power.hasInternalBatteries ? "battery-missing" : "battery-" + Math.max(0, Math.min(100, Math.round(power.percent / 10) * 10)) + (power.pluggedIn ? "-charging" : "")
        label: power.hasInternalBatteries ? i18n("Battery — %1%", power.percent) : i18n("Battery")
        selected: popup.visible
        onClicked: popup.visible = !popup.visible
    }
    Connections { target: Plasmoid; function onActivated() { popup.visible = !popup.visible; } }
    Controls.ControlDialog {
        id: popup
        title: "mttkde-battery"
        visible: false
        visualParent: root
        location: Plasmoid.location
        surfaces: menu.surfaces
        mainItem: Controls.StatusMenuPopup { id: menu; panelHighlight: false; source: Qt.resolvedUrl("../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui/BatteryView.qml"); width: implicitWidth; height: implicitHeight }
        onVisibleChanged: if (visible) { requestActivate(); menu.forceActiveFocus(); }
    }
}
