// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.notificationmanager as Notifications
import org.kde.mac.tahoe.launcher as Native
import "NotificationContrast.js" as Contrast
Page {
    id: view
    title: ""
    property color backdropColor: "transparent"
    property bool standalone: false
    spacing: 6
    readonly property var surfaces: {
        const offset = list.contentY;
        const extent = list.contentHeight;
        const areas = [];
        for (const delegate of list.contentItem.children) {
            if (delegate.objectName !== "historyNotificationDelegate" || !delegate.visible) continue;
            const card = delegate.surface;
            const point = list.mapToItem(view, delegate.x, delegate.y - list.contentY);
            const layers = card.surfaces;
            for (let i = 0; i < layers.length; ++i) {
                const area = layers[i];
                const top = Math.max(point.y + area.y, scroll.y);
                const bottom = Math.min(point.y + area.y + area.height, scroll.y + scroll.height);
                if (bottom > top)
                    areas.push({x:point.x+area.x, y:top, width:area.width,
                        height:bottom-top, radius:area.radius, fill:i === 0 ? card.fillColor : undefined});
            }
            if (card.contentItem.closeVisible)
                // Input only: glass here would merge with the card corner it overlaps.
                areas.push({x:point.x-6, y:point.y-4, width:20, height:20, radius:10, glass:false});
        }
        areas.push({x:clear.mapToItem(view,0,0).x, y:clear.mapToItem(view,0,0).y, width:20, height:20, radius:10});
        return areas;
    }
    Native.GlassSettings { id: inkSettings; component: "notifications" }
    readonly property color componentInk: {
        const observations = [];
        let uncovered = view.width * view.height;
        for (const area of view.surfaces) {
            if (area.fill === undefined) continue;
            const size = area.width * area.height;
            observations.push({backdrop: view.backdropColor, fill: area.fill, area: size});
            uncovered -= size;
        }
        observations.push({backdrop: view.backdropColor, fill: Qt.rgba(0,0,0,0), area: Math.max(0, uncovered)});
        return inkSettings.notificationFamily(Contrast.preferredText(view.Kirigami.Theme.textColor), observations);
    }
    property var history: nativeHistory
    Notifications.Settings { id: settings }
    Notifications.Notifications {
        id: nativeHistory
        showExpired: true
        showDismissed: true
        showJobs: true
        sortMode: Notifications.Notifications.SortByDate
        sortOrder: Qt.DescendingOrder
        groupMode: Notifications.Notifications.GroupApplicationsFlat
        groupLimit: 1
        blacklistedDesktopEntries: settings.historyBlacklistedApplications
        blacklistedNotifyRcNames: settings.historyBlacklistedServices
    }
    Notifications.Notifications {
        id: details
        showExpired: true
        showDismissed: true
        showJobs: true
        groupMode: Notifications.Notifications.GroupDisabled
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.preferredHeight: 24
        NotificationBackdropLabel {
            id: heading
            objectName: "notificationCenterHeading"
            text: view.standalone ? i18n("Notification Center") : i18n("Notifications")
            font.family: "SF Pro Display"; font.pixelSize: 18; font.weight: Font.DemiBold
            backdropColor: view.backdropColor
            componentInk: view.componentInk
            floating: view.standalone
            Layout.fillWidth: true
        }
        QQC.AbstractButton {
            id: clear
            objectName: "clearHistory"
            implicitWidth: 20; implicitHeight: 20
            Accessible.name: i18n("Clear History")
            enabled: view.history.expiredNotificationsCount > 0
            background: Rectangle {
                radius: 10
                color: heading.color.r > .5 ? Qt.rgba(0,0,0,clear.hovered ? .7 : .5)
                                           : Qt.rgba(1,1,1,clear.hovered ? .7 : .5)
            }
            contentItem: Kirigami.Icon { source: Qt.resolvedUrl("symbols/mttkde-control-notification-close.svg"); isMask: true; color: heading.color; opacity: .53 }
            onClicked: view.history.clear(Notifications.Notifications.ClearExpired)
        }
    }
    NotificationBackdropLabel {
        text: i18n("No notifications")
        backdropColor: view.backdropColor
        componentInk: view.componentInk
        floating: view.standalone
        visible: view.history.count === 0
    }
    Item {
        id: scroll
        Layout.leftMargin: -8; Layout.rightMargin: -8
        Layout.topMargin: -8; Layout.bottomMargin: -8
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(560, list.contentHeight) + 16
        visible: view.history.count > 0
        clip: true
        ListView {
            id: list
            x: 8; y: 8
            width: parent.width - 16; height: parent.height - 16
            boundsBehavior: Flickable.StopAtBounds
            QQC.ScrollBar.vertical: QQC.ScrollBar {}
            spacing: 0
            model: view.history
            delegate: Item {
                id: entry
                objectName: "historyNotificationDelegate"
                required property var model
                required property int index
                readonly property bool stacked: !!model.isGroup && !model.isGroupExpanded
                readonly property var surface: card
                visible: !model.isInGroup || model.isGroupExpanded
                width: ListView.view.width
                height: visible ? card.implicitHeight + 6 : 0
                NotificationStackSurface {
                    id: card
                    width: parent.width; height: implicitHeight
                    depth: entry.stacked ? Math.min(2, Math.max(1, Number(entry.model.groupChildrenCount || 2)-1)) : 0
                    contentItem: NotificationCard {
                        model: entry.model
                        index: entry.index
                        history: view.history
                        previewHistory: details
                        backdropColor: view.backdropColor
                        componentInk: view.componentInk
                        surfaceColor: card.fillColor
                    }
                }
            }
        }
    }
    SettingsLink { id: preferences; visible: !view.standalone; text: i18n("Notification Settings…"); module: "kcm_notifications" }
    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: (point,button) => contextMenu.popup(point.position.x, point.position.y)
    }
    QQC.Menu {
        id: contextMenu
        font.family: "SF Pro Display"; font.pixelSize: 13
        QQC.MenuItem { text: i18n("Notification Settings…"); onTriggered: preferences.clicked() }
    }
}
