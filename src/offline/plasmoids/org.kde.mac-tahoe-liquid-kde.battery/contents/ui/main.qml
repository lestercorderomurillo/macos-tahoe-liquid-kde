// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.private.battery as Power
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.mac.tahoe.launcher as Native
import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Controls
PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Power.BatteryControlModel { id: power }
    preferredRepresentation: fullRepresentation
    compactRepresentation: null
    fullRepresentation: Controls.PanelButton {
        symbol: !power.hasInternalBatteries ? "battery-missing" : "battery-" + Math.max(0, Math.min(100, Math.round(power.percent / 10) * 10)) + (power.pluggedIn ? "-charging" : "")
        label: power.hasInternalBatteries ? i18n("Battery — %1%", power.percent) : i18n("Battery")
        selected: popup.visible
        onClicked: popup.visible = !popup.visible
    }
    Connections { target: Plasmoid; function onActivated() { popup.visible = !popup.visible; } }
    PlasmaCore.Dialog {
        id: popup
        title: "mttkde-battery"
        visible: false
        visualParent: root
        location: Plasmoid.location
        type: PlasmaCore.Dialog.AppletPopup
        flags: Qt.WindowStaysOnTopHint
        backgroundHints: PlasmaCore.Dialog.NoBackground
        hideOnWindowDeactivate: true
        mainItem: Controls.StatusMenuPopup { id: menu; source: Qt.resolvedUrl("../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui/BatteryView.qml"); width: implicitWidth; height: implicitHeight }
        onVisibleChanged: if (visible) { requestActivate(); menu.forceActiveFocus(); }
    }
    Native.ControlGlass { window: popup; surfaces: menu.surfaces }
}
