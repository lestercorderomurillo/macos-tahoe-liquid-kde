// SPDX-License-Identifier: GPL-3.0-or-later
pragma Singleton
import QtQuick
import QtQuick.Window
import org.kde.notificationmanager as Notifications
import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Controls

QtObject {
    id: service
    // One frontend per Plasma process, even with a bar on every display.
    property var hosts: []
    readonly property var host: hosts.length ? hosts[0] : null
    readonly property bool historyVisible: hosts.some(item => item.historyVisible === true)
    onHistoryVisibleChanged: position()
    function markSeen() {
        for (let i = members.count - 1; i >= 0; --i) {
            const index = members.index(i, 0);
            members.setData(index, true, Notifications.Notifications.ReadRole);
            members.setData(index, true, Notifications.Notifications.ExpiredRole);
        }
    }
    function expireStack(row) {
        const selected = popups.index(row, 0);
        const grouped = popups.data(selected, Notifications.Notifications.IsGroupRole);
        const roles = [Notifications.Notifications.ApplicationNameRole,
            Notifications.Notifications.DesktopEntryRole, Notifications.Notifications.OriginNameRole];
        const identity = roles.map(role => popups.data(selected, role));
        const id = popups.data(selected, Notifications.Notifications.IdRole);
        for (let i = members.count - 1; i >= 0; --i) {
            const index = members.index(i, 0);
            if (grouped ? !roles.every((role, n) => members.data(index, role) === identity[n])
                        : members.data(index, Notifications.Notifications.IdRole) !== id) continue;
            const actions = members.data(index, Notifications.Notifications.ActionNamesRole) || [];
            if (members.data(index, Notifications.Notifications.ResidentRole)
                    || (actions.length && !members.data(index, Notifications.Notifications.TransientRole)))
                members.setData(index, true, Notifications.Notifications.ExpiredRole);
            else members.expire(index);
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
        groupMode: Notifications.Notifications.GroupApplicationsFlat
        groupLimit: 1
        sortMode: Notifications.Notifications.SortByDate
        sortOrder: Qt.DescendingOrder
        window: service.host ? service.host.Window.window : null
    }
    // Keep a stable ungrouped view for member mutations. Switching KDE's
    // grouping proxy on a live model can detach its collapsing proxy.
    property Notifications.Notifications members: Notifications.Notifications {
        showExpired: false
        showDismissed: false
        showJobs: false
        showAddedDuringInhibition: popups.showAddedDuringInhibition
        blacklistedDesktopEntries: popups.blacklistedDesktopEntries
        blacklistedNotifyRcNames: popups.blacklistedNotifyRcNames
        whitelistedDesktopEntries: popups.whitelistedDesktopEntries
        whitelistedNotifyRcNames: popups.whitelistedNotifyRcNames
        urgencies: popups.urgencies
        sortMode: Notifications.Notifications.SortByDate
        sortOrder: Qt.DescendingOrder
        groupMode: Notifications.Notifications.GroupDisabled
    }
    property var soundedIds: []
    property var expiryDeadlines: ({})
    function position() {
        let y = geometry.y + available.y + 16;
        for (let i = 0; i < windows.count; ++i) {
            const popup = windows.objectAt(i);
            if (!popup) continue;
            if (!popup.displayable) { popup.visible = false; continue; }
            popup.x = geometry.x + available.x + available.width - popup.width - 6;
            popup.y = y - 10;
            popup.visible = !!host && !historyVisible && available.width > 0 && y + popup.height < geometry.y + available.y + available.height;
            if (popup.visible && popup.model.type === Notifications.Notifications.NotificationType) {
                const key = popup.notificationId + ":" + Number(popup.model.updated);
                if (popup.interacting) {
                    delete expiryDeadlines[key];
                } else if (popup.expiry.eligible) {
                    if (!expiryDeadlines[key]) {
                        const keys = Object.keys(expiryDeadlines);
                        if (keys.length >= 256) delete expiryDeadlines[keys[0]];
                        expiryDeadlines[key] = Date.now() + (popup.model.timeout > 0
                            ? popup.model.timeout : settings.popupTimeout);
                    }
                    // A group becoming a single message can replace its window.
                    // Retain the original deadline instead of restarting expiry.
                    popup.remainingTimeout = Math.max(1, expiryDeadlines[key] - Date.now());
                }
            }
            // Group formation, expansion and model resets can recreate delegates.
            // Sound each arriving notification once, including updates to a stack.
            if (popup.visible && !soundedIds.includes(popup.notificationId)) {
                soundedIds = soundedIds.slice(-255).concat([popup.notificationId]);
                popups.playSoundHint(popups.index(popup.index, 0));
            }
            y += popup.height - 14;
        }
    }
    onAvailableChanged: position()
    onGeometryChanged: position()
    property Instantiator windows: Instantiator {
        id: windows
        model: service.host ? service.popups : null
        delegate: NotificationPopup {
            id: notice
            history: service.popups
            settings: service.settings
            members: service.members
            cardWidth: Math.min(344, service.available.width - 32)
            foregroundColor: service.host ? service.host.notificationTextColor : "black"
            backgroundColor: service.host ? service.host.notificationBackgroundColor : "white"
            disabledColor: service.host ? service.host.notificationDisabledColor : "gray"
            onExpiryRequested: service.expireStack(index)
            onRepositionRequested: Qt.callLater(service.position)
        }
        onObjectAdded: (index, object) => {
            service.position();
            if (service.historyVisible) Qt.callLater(service.markSeen);
        }
        onObjectRemoved: (index, object) => {
            service.popups.startTimeout(Number(object.notificationId));
            Qt.callLater(service.position);
        }
    }
}
