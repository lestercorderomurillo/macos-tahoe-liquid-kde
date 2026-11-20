// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.kirigami as Kirigami
import "."
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.mac.tahoe.launcher as Native
import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Controls
PlasmoidItem {
    id: root
    readonly property color notificationTextColor: Kirigami.Theme.textColor
    readonly property color notificationBackgroundColor: Kirigami.Theme.backgroundColor
    readonly property color notificationDisabledColor: Kirigami.Theme.disabledTextColor
    readonly property bool historyVisible: popup.visible
    Component.onCompleted: NotificationPopups.adopt(root)
    Component.onDestruction: NotificationPopups.forget(root)
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation
    compactRepresentation: null
    fullRepresentation: Controls.PanelButton {
        symbol: "notifications"
        label: i18n("Notifications")
        selected: popup.visible
        onClicked: popup.visible = !popup.visible
    }
    Connections { target: Plasmoid; function onActivated() { popup.visible = !popup.visible; } }
    Native.NotificationBanner {
        id: popup
        // Notification history and banners share the popup material.
        title: "mttkde-notifications"
        visible: false
        takeFocus: true
        width: 364; height: history.implicitHeight + 20
        property bool hadFocus: false
        onActiveChanged: {
            if (active) hadFocus = true;
            else if (hadFocus) visible = false;
        }
        mainItem: Item {
            id: tile
            width: popup.width; height: popup.height
            Kirigami.Theme.inherit: false
            Kirigami.Theme.textColor: root.notificationTextColor
            Kirigami.Theme.backgroundColor: root.notificationBackgroundColor
            Kirigami.Theme.disabledTextColor: root.notificationDisabledColor
            Controls.NotificationsView {
                id: history
                x: 10; y: 10; width: 344; height: implicitHeight
                standalone: true
                backdropColor: popup.backdropColor
                focus: true
                Keys.onEscapePressed: popup.visible = false
            }
        }
        onVisibleChanged: if (visible) {
            hadFocus = false;
            NotificationPopups.markSeen(); requestActivate(); history.forceActiveFocus();
            const screen = root.plasmoid.containment.screenGeometry;
            const available = root.plasmoid.containment.availableScreenRect;
            popup.x = screen.x + available.x + available.width - popup.width - 6;
            popup.y = screen.y + available.y + 6;
        }
    }
    Native.ControlGlass {
        window: popup
        maskWindow: false
        surfaces: history.surfaces.map(area => ({x:area.x+10,y:area.y+10,width:area.width,height:area.height,radius:area.radius,glass:area.glass !== false}))
    }
}
