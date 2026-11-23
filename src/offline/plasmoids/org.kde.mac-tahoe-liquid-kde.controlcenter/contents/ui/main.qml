// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import "MenuBarSync.js" as MenuBarSync
PlasmoidItem {
    id: root
    SettingsEntry { id: settingsEntry; widgetId: Plasmoid.id }
    Plasmoid.hasConfigurationInterface: !settingsEntry.available
    Plasmoid.contextualActions: [settingsEntry]
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    StatusTrayStyle {
        panelItem: root
        wallpaperTint: root.inMenuBar
    }
    preferredRepresentation: fullRepresentation
    compactRepresentation: null
    fullRepresentation: PanelButton {
        wallpaperTint: Plasmoid.location === PlasmaCore.Types.TopEdge
        symbol: Qt.resolvedUrl("controlcenter.svg")
        label: i18n("Control Center")
        selected: popup.visible
        onClicked: popup.toggle()
    }
    toolTipMainText: popup.visible ? "" : i18n("Control Center")
    toolTipSubText: ""
    Connections { target: Plasmoid; function onActivated() { popup.toggle(); } }
    // Keep the menu bar the same on every screen: tray icons and widget settings.
    property var menuBar: null
    readonly property bool inMenuBar: Plasmoid.location === PlasmaCore.Types.TopEdge && !!Plasmoid.containment
    function joinMenuBar() {
        if (menuBar) MenuBarSync.unregister(menuBar);
        menuBar = inMenuBar ? MenuBarSync.register(Plasmoid.containment) : null;
    }
    onInMenuBarChanged: joinMenuBar()
    Component.onCompleted: joinMenuBar()
    Component.onDestruction: if (menuBar) MenuBarSync.unregister(menuBar)
    Connections {
        target: root.menuBar ? Plasmoid.containment : null
        function onAppletAdded() { MenuBarSync.refresh(root.menuBar); }
        function onAppletRemoved() { MenuBarSync.unwatchAll(root.menuBar); MenuBarSync.refresh(root.menuBar); }
    }
    ControlDialog {
        id: popup
        // The 200 ms macOS Tahoe zoom and fade are run by the
        // mttkde_controlcenter_transition KWin effect, at display rate.
        function toggle() { visible = !visible; }
        function dismiss() { visible = false; }
        title: "mttkde-control-center"
        // The transparent shadow margin must not let the pointer reach windows below.
        inputOnGlassOnly: false
        visible: false
        visualParent: root
        location: Plasmoid.location
        surfaces: controls.surfaces
        mainItem: ControlView {
            id: controls
            shadowMargin: 170
            preferences: Plasmoid.configuration
            openControlSettings: settingsEntry.available ? () => settingsEntry.trigger() : null
            width: implicitWidth
            height: implicitHeight
            onCloseRequested: popup.dismiss()
        }
        onVisibleChanged: { if (visible) { requestActivate(); controls.forceActiveFocus(); } else controls.section = ""; }
    }
}
