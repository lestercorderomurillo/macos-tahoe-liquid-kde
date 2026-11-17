// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.notificationmanager as Notifications
import org.kde.mac.tahoe.launcher as Native
import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Controls

Native.NotificationBanner {
    id: banner
    required property var model
    required property int index
    required property var history
    required property var settings
    property real cardWidth: 344
    property color foregroundColor: "black"
    property color backgroundColor: "white"
    property color disabledColor: "gray"
    signal repositionRequested()
    readonly property string notificationId: model.notificationId
    title: "mttkde-notifications"
    width: cardWidth + 20
    height: tile.implicitHeight + 20
    takeFocus: card.interacting
    isCritical: model.urgency === Notifications.Notifications.CriticalUrgency
    mainItem: Item {
        width: banner.width; height: banner.height
        // QQuickWindow has no Plasma Dialog palette bridge. Inherit the live
        // bar palette explicitly, including for windows that are already open.
        Kirigami.Theme.inherit: false
        Kirigami.Theme.textColor: banner.foregroundColor
        Kirigami.Theme.backgroundColor: banner.backgroundColor
        Kirigami.Theme.disabledTextColor: banner.disabledColor
        Controls.NotificationSurface {
            id: tile
            x: 10; y: 10
            width: banner.width - 20
            height: implicitHeight
            contentItem: Controls.NotificationCard {
                id: card
                model: banner.model
                index: banner.index
                history: banner.history
                compact: true
            }
        }
    }
    property Native.ControlGlass glass: Native.ControlGlass {
        window: banner
        surfaces: [{x:10, y:10, width:tile.width, height:tile.height, radius:tile.cornerRadius}].concat(
            card.closeVisible ? [{x:4, y:6, width:20, height:20, radius:10}] : [])
    }
    property Timer expiry: Timer {
        interval: banner.model.timeout > 0 ? banner.model.timeout : banner.settings.popupTimeout
        running: banner.visible && banner.model.timeout !== 0
            && !(banner.isCritical && banner.model.timeout < 0) && !card.interacting
            && !(banner.settings.permanentJobPopups && banner.model.type === Notifications.Notifications.JobType)
        onTriggered: {
            // Preserve resident/actionable notifications for the history frontend.
            if (banner.model.resident || (banner.model.actionNames.length && !banner.model.transient))
                banner.model.expired = true;
            else banner.history.expire(banner.history.index(banner.index, 0));
        }
    }
    property Connections updates: Connections {
        target: banner.model
        ignoreUnknownSignals: true
        function onUpdatedChanged() { banner.expiry.restart(); }
    }
    onHeightChanged: banner.repositionRequested()
    onWidthChanged: banner.repositionRequested()
    Component.onCompleted: banner.history.stopTimeout(banner.history.index(index, 0))
}
