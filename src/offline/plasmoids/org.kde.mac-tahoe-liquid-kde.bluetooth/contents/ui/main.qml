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
        symbol: "preferences-system-bluetooth"
        label: i18n("Bluetooth")
        selected: popup.visible
        onClicked: popup.visible = !popup.visible
    }
    Connections { target: Plasmoid; function onActivated() { popup.visible = !popup.visible; } }
    Controls.ControlDialog {
        id: popup
        title: "mttkde-bluetooth"
        visible: false
        visualParent: root
        location: Plasmoid.location
        surfaces: menu.surfaces
        mainItem: Controls.StatusMenuPopup {
            id: menu
            source: Qt.resolvedUrl("../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui/BluetoothView.qml")
            width: implicitWidth
            height: implicitHeight
        }
        onVisibleChanged: if (visible) { requestActivate(); menu.forceActiveFocus(); }
    }
}
