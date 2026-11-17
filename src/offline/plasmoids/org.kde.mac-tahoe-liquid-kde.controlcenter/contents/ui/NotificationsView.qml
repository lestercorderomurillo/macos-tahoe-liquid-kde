// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.notificationmanager as Notifications
Page {
    id: view
    title: ""
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
            const top = Math.max(point.y, scroll.y);
            const bottom = Math.min(point.y + card.height, scroll.y + scroll.height);
            if (bottom <= top) continue;
            areas.push({x:point.x, y:top, width:card.width, height:bottom-top, radius:card.cornerRadius});
            if (delegate.stacked)
                areas.push({x:point.x+8,y:bottom-8,width:card.width-16,height:16,radius:8});
            if (card.contentItem.closeVisible)
                areas.push({x:point.x-6, y:point.y-4, width:20, height:20, radius:10});
        }
        areas.push({x:clear.mapToItem(view,0,0).x, y:clear.mapToItem(view,0,0).y, width:20, height:20, radius:10});
        return areas;
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
    RowLayout {
        Layout.fillWidth: true
        Layout.preferredHeight: 24
        Text {
            text: view.standalone ? i18n("Notification Center") : i18n("Notifications")
            font.family: "SF Pro Display"; font.pixelSize: 18; font.weight: Font.DemiBold
            color: view.standalone ? "white" : Kirigami.Theme.textColor
            Layout.fillWidth: true
            layer.enabled: view.standalone
            layer.effect: MultiEffect { shadowEnabled: true; shadowBlur: 0.25; shadowColor: "#66000000"; shadowVerticalOffset: 1 }
        }
        QQC.AbstractButton {
            id: clear
            objectName: "clearHistory"
            implicitWidth: 20; implicitHeight: 20
            Accessible.name: i18n("Clear History")
            enabled: view.history.expiredNotificationsCount > 0
            background: Rectangle {
                radius: 10
                color: clear.hovered ? Qt.rgba(1,1,1,.7) : Qt.rgba(1,1,1,.5)
            }
            contentItem: Kirigami.Icon { source: Qt.resolvedUrl("symbols/mttkde-control-notification-close.svg"); isMask: true; color: "#88000000" }
            onClicked: view.history.clear(Notifications.Notifications.ClearExpired)
        }
    }
    ControlLabel {
        text: i18n("No notifications")
        color: view.standalone ? "white" : Kirigami.Theme.textColor
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
                height: visible ? card.implicitHeight + (stacked ? 8 : 0) + 6 : 0
                Repeater {
                    model: entry.stacked ? 2 : 0
                    Item {
                        required property int index
                        x: (2-index)*4; y: card.height+(1-index)*4
                        width: entry.width-x*2; height: 4
                        clip: true
                        NotificationSurface {
                            y: 4-card.height
                            width: parent.width; height: card.height
                            contentItem: Item {}
                        }
                    }
                }
                NotificationSurface {
                    id: card
                    width: parent.width; height: implicitHeight
                    contentItem: NotificationCard {
                        model: entry.model
                        index: entry.index
                        history: view.history
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
