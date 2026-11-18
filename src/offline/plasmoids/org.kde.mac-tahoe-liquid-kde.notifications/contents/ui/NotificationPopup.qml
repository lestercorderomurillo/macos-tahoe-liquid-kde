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
    property var members: history
    property int remainingTimeout: 0
    readonly property bool interacting: card.interacting
    property real cardWidth: 344
    property color foregroundColor: "black"
    property color backgroundColor: "white"
    property color disabledColor: "gray"
    signal repositionRequested()
    signal expiryRequested()
    readonly property string notificationId: model.notificationId
    readonly property bool displayable: !model.isInGroup || model.isGroupExpanded
    onDisplayableChanged: banner.repositionRequested()
    onNotificationIdChanged: banner.repositionRequested()
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
        Controls.NotificationStackSurface {
            id: tile
            x: 10; y: 10
            width: banner.width - 20
            height: implicitHeight
            depth: banner.model.isGroup && !banner.model.isGroupExpanded
                ? Math.min(2, Math.max(1, Number(banner.model.groupChildrenCount || 2)-1)) : 0
            contentItem: Controls.NotificationCard {
                id: card
                model: banner.model
                index: banner.index
                history: banner.history
                previewHistory: banner.members
                backdropColor: banner.backdropColor
                surfaceColor: tile.fillColor
                compact: true
            }
        }
    }
    property Native.ControlGlass glass: Native.ControlGlass {
        window: banner
        surfaces: tile.surfaces.map(area => ({x:area.x+10, y:area.y+10,
            width:area.width, height:area.height, radius:area.radius})).concat(
            card.closeVisible ? [{x:4, y:6, width:20, height:20, radius:10}] : [])
    }
    property Timer expiry: Timer {
        objectName: "notificationExpiry"
        interval: banner.remainingTimeout > 0 ? banner.remainingTimeout
            : banner.model.timeout > 0 ? banner.model.timeout : banner.settings.popupTimeout
        readonly property bool eligible: banner.visible && banner.model.timeout !== 0
            && !(banner.model.isGroup && banner.model.isGroupExpanded)
            && !(banner.isCritical && banner.model.timeout < 0) && !card.interacting
            && !(banner.settings.permanentJobPopups && banner.model.type === Notifications.Notifications.JobType)
        running: eligible
        onEligibleChanged: banner.repositionRequested()
        onTriggered: {
            if (banner.model.type === Notifications.Notifications.JobType)
                banner.history.expire(banner.history.index(banner.index, 0));
            else banner.expiryRequested();
        }
    }
    property Connections updates: Connections {
        target: banner.model
        ignoreUnknownSignals: true
        function onUpdatedChanged() {
            if (banner.expiry.eligible && banner.model.type === Notifications.Notifications.JobType)
                banner.expiry.restart();
            banner.repositionRequested();
        }
    }
    onHeightChanged: banner.repositionRequested()
    onWidthChanged: banner.repositionRequested()
    Component.onCompleted: banner.history.stopTimeout(banner.history.index(index, 0))
}
