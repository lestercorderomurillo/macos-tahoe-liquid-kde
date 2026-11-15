// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.private.battery as Power
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Controls
PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Power.BatteryControlModel { id: power }
    preferredRepresentation: compactRepresentation
    compactRepresentation: Controls.PanelButton {
        symbol: !power.hasInternalBatteries ? "battery-missing" : "battery-" + Math.max(0, Math.min(100, Math.round(power.percent / 10) * 10)) + (power.pluggedIn ? "-charging" : "")
        label: power.hasInternalBatteries ? i18n("Battery — %1%", power.percent) : i18n("Battery")
        selected: root.expanded
        onClicked: root.expanded = !root.expanded
    }
    fullRepresentation: Controls.BatteryView {}
}
