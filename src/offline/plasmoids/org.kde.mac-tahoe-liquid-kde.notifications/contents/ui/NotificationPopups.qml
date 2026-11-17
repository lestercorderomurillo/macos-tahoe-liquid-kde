// SPDX-License-Identifier: GPL-3.0-or-later
pragma Singleton
import QtQuick
import QtQuick.Window
import org.kde.notificationmanager as Notifications
import org.kde.mac.tahoe.launcher as Native
import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Controls

QtObject {
    id: service
    // One frontend per Plasma process, even with a bar on every display.
    property var hosts: []
    readonly property var host: hosts.length ? hosts[0] : null
    readonly property bool historyVisible: hosts.some(item => item.historyVisible === true)
    onHistoryVisibleChanged: position()
    function markSeen() {
        for (let i = windows.count - 1; i >= 0; --i) {
            const popup = windows.objectAt(i);
            if (popup && popup.model.type === Notifications.Notifications.NotificationType) {
                popup.model.read = true;
                popup.model.expired = true;
            }
        }
    }
    function adopt(item) { hosts = hosts.concat([item]); }
    function forget(item) { hosts = hosts.filter(value => value !== item); }
    property date now: new Date()
    property Timer clock: Timer {
        interval: 1000; running: !!service.host; repeat: true
        onTriggered: service.now = new Date()
    }
    property var settings: nativeSettings
    property Notifications.Settings nativeSettings: Notifications.Settings {}
    readonly property bool inhibited: settings.notificationsInhibitedUntil > now
        || settings.notificationsInhibitedByApplication
        || (settings.inhibitNotificationsWhenFullscreen && settings.fullscreenFocused)
        || (settings.inhibitNotificationsWhenScreensMirrored && settings.screensMirrored)
    onInhibitedChanged: if (host) Notifications.Server.inhibited = inhibited
    onHostChanged: Notifications.Server.inhibited = !!host && inhibited
    readonly property rect available: host ? host.plasmoid.containment.availableScreenRect : Qt.rect(0, 0, 0, 0)
    readonly property rect geometry: host ? host.plasmoid.containment.screenGeometry : Qt.rect(0, 0, 0, 0)
    property Notifications.Notifications popups: Notifications.Notifications {
        limit: Math.max(1, Math.ceil(service.available.height / 80))
        showExpired: false
        showDismissed: false
        showAddedDuringInhibition: false
        showJobs: service.settings.jobsInNotifications
        blacklistedDesktopEntries: service.settings.popupBlacklistedApplications
        blacklistedNotifyRcNames: service.settings.popupBlacklistedServices
        whitelistedDesktopEntries: service.inhibited ? service.settings.doNotDisturbPopupWhitelistedApplications : []
        whitelistedNotifyRcNames: service.inhibited ? service.settings.doNotDisturbPopupWhitelistedServices : []
        urgencies: (service.inhibited ? 0 : Notifications.Notifications.NormalUrgency)
            | (!service.inhibited || service.settings.criticalPopupsInDoNotDisturbMode ? Notifications.Notifications.CriticalUrgency : 0)
            | (!service.inhibited && service.settings.lowPriorityPopups ? Notifications.Notifications.LowUrgency : 0)
        groupMode: Notifications.Notifications.GroupDisabled
        sortMode: Notifications.Notifications.SortByDate
        sortOrder: Qt.DescendingOrder
        window: service.host ? service.host.Window.window : null
    }
    function position() {
        let y = geometry.y + available.y + 16;
        for (let i = 0; i < windows.count; ++i) {
            const popup = windows.objectAt(i);
            if (!popup) continue;
            popup.x = geometry.x + available.x + available.width - popup.width - 6;
            popup.y = y - 10;
            popup.visible = !!host && !historyVisible && available.width > 0 && y + popup.height < geometry.y + available.y + available.height;
            y += popup.height - 14;
        }
    }
    onAvailableChanged: position()
    onGeometryChanged: position()
    property Instantiator windows: Instantiator {
        id: windows
        model: service.host ? service.popups : null
        delegate: NotificationPopup {
            history: service.popups
            settings: service.settings
            cardWidth: Math.min(344, service.available.width - 32)
            foregroundColor: service.host ? service.host.notificationTextColor : "black"
            backgroundColor: service.host ? service.host.notificationBackgroundColor : "white"
            disabledColor: service.host ? service.host.notificationDisabledColor : "gray"
            onRepositionRequested: Qt.callLater(service.position)
        }
        onObjectAdded: (index, object) => {
            service.position();
            if (service.historyVisible) Qt.callLater(service.markSeen);
            service.popups.playSoundHint(service.popups.index(index, 0));
        }
        onObjectRemoved: (index, object) => {
            service.popups.startTimeout(Number(object.notificationId));
            Qt.callLater(service.position);
        }
    }
}
