// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.mac.tahoe.launcher as Native
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    StatusTrayStyle { panelItem: root }
    preferredRepresentation: fullRepresentation
    compactRepresentation: null
    fullRepresentation: PanelButton {
        symbol: Qt.resolvedUrl("controlcenter.svg")
        label: i18n("Control Center")
        selected: popup.visible
        onClicked: popup.toggle()
    }
    toolTipMainText: popup.visible ? "" : i18n("Control Center")
    toolTipSubText: ""
    Connections { target: Plasmoid; function onActivated() { popup.toggle(); } }
    ControlDialog {
        id: popup
        // The 200 ms macOS Tahoe zoom and fade are run by the
        // mttkde_controlcenter_transition KWin effect, at display rate.
        function toggle() { visible = !visible; }
        function dismiss() { visible = false; }
        title: "mttkde-control-center"
        Native.GlassSettings { id: inkSettings; component: "control-center"; window: popup }
        adaptiveForeground: inkSettings.dynamicTinting
        regionalForeground: true
        // The transparent shadow margin must not let the pointer reach windows below.
        inputOnGlassOnly: false
        visible: false
        visualParent: root
        location: Plasmoid.location
        surfaces: controls.surfaces
        mainItem: ControlView { id: controls; shadowMargin: 170; preferences: Plasmoid.configuration; width: implicitWidth; height: implicitHeight; onCloseRequested: popup.dismiss() }
        onVisibleChanged: { if (visible) { requestActivate(); controls.forceActiveFocus(); } else controls.section = ""; }
    }
}
