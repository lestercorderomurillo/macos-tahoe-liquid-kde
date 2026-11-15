// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.notificationmanager as Notifications
Page {
    id: view
    title: i18n("Notifications")
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
        groupLimit: 3
        blacklistedDesktopEntries: settings.historyBlacklistedApplications
        blacklistedNotifyRcNames: settings.historyBlacklistedServices
    }
    FocusSwitch { Layout.fillWidth: true }
    ControlLabel { text: i18n("No notifications"); visible: view.history.count === 0 }
    QQC.ScrollView {
        Layout.fillWidth: true
        Layout.preferredHeight: Kirigami.Units.gridUnit * 20
        clip: true
        ListView {
            id: list
            spacing: Kirigami.Units.smallSpacing * 2
            model: view.history
            delegate: ColumnLayout {
                id: row
                required property var model
                required property int index
                width: ListView.view.width
                spacing: Kirigami.Units.smallSpacing
                function itemIndex() { return view.history.index(index, 0); }
                RowLayout {
                    Layout.fillWidth: true
                    Kirigami.Icon { source: row.model.applicationIconName; implicitWidth: Kirigami.Units.iconSizes.small; implicitHeight: implicitWidth }
                    ControlLabel { Layout.fillWidth: true; text: row.model.applicationName || ""; elide: Text.ElideRight; font.weight: Font.DemiBold }
                    QQC.ToolButton { font.family: "SF Pro Text"; font.pixelSize: 13;
                        objectName: "notificationGroup"; text: row.model.isGroupExpanded ? i18n("Collapse") : i18n("Expand")
                        visible: !!row.model.isGroup
                        onClicked: view.history.setData(row.itemIndex(), !row.model.isGroupExpanded, Notifications.Notifications.IsGroupExpandedRole)
                    }
                    QQC.ToolButton { font.family: "SF Pro Text"; font.pixelSize: 13; objectName: "notificationDismiss"; icon.name: "window-close"; text: i18n("Dismiss"); display: QQC.AbstractButton.IconOnly; Accessible.name: text; visible: row.model.closable; onClicked: view.history.close(row.itemIndex()) }
                }
                ControlLabel { Layout.fillWidth: true; visible: !row.model.isGroup; text: row.model.summary || ""; textFormat: Text.PlainText; wrapMode: Text.WordWrap; font.weight: Font.DemiBold }
                ControlLabel { Layout.fillWidth: true; visible: !row.model.isGroup; text: row.model.body || ""; textFormat: Text.StyledText; wrapMode: Text.WordWrap;  onLinkActivated: link => Qt.openUrlExternally(link) }
                QQC.ProgressBar { Layout.fillWidth: true; visible: row.model.type === Notifications.Notifications.JobType; from: 0; to: 100; value: row.model.percentage || 0 }
                Flow {
                    Layout.fillWidth: true; spacing: Kirigami.Units.smallSpacing
                    QQC.Button { font.family: "SF Pro Text"; font.pixelSize: 13; objectName: "notificationOpen"; text: i18n("Open"); visible: row.model.hasDefaultAction; onClicked: view.history.invokeDefaultAction(row.itemIndex()) }
                    Repeater {
                        model: row.model.actionNames || []
                        delegate: QQC.Button { font.family: "SF Pro Text"; font.pixelSize: 13;
                            objectName: "notificationAction"
                            required property string modelData
                            required property int index
                            text: row.model.actionLabels[index] || modelData
                            onClicked: view.history.invokeAction(row.itemIndex(), modelData)
                        }
                    }
                    QQC.Button { font.family: "SF Pro Text"; font.pixelSize: 13; objectName: "notificationPause"; text: row.model.jobState === Notifications.Notifications.JobStateSuspended ? i18n("Resume") : i18n("Pause"); visible: row.model.suspendable; onClicked: row.model.jobState === Notifications.Notifications.JobStateSuspended ? view.history.resumeJob(row.itemIndex()) : view.history.suspendJob(row.itemIndex()) }
                    QQC.Button { font.family: "SF Pro Text"; font.pixelSize: 13; objectName: "notificationCancel"; text: i18n("Cancel Job"); visible: row.model.killable; onClicked: view.history.killJob(row.itemIndex()) }
                }
                RowLayout {
                    visible: row.model.hasReplyAction
                    QQC.TextField { font.family: "SF Pro Text"; font.pixelSize: 13; id: reply; objectName: "notificationReply"; Layout.fillWidth: true; placeholderText: i18n("Reply…"); Accessible.name: placeholderText }
                    QQC.Button { font.family: "SF Pro Text"; font.pixelSize: 13; objectName: "notificationSend"; text: i18n("Send"); enabled: reply.text.trim().length > 0; onClicked: { view.history.reply(row.itemIndex(), reply.text, Notifications.Notifications.None); reply.clear(); } }
                }
            }
        }
    }
    QQC.Button { font.family: "SF Pro Text"; font.pixelSize: 13; objectName: "clearHistory"; text: i18n("Clear History"); enabled: view.history.expiredNotificationsCount > 0; onClicked: view.history.clear(Notifications.Notifications.ClearExpired) }
    SettingsLink { text: i18n("Notification Settings…"); module: "kcm_notifications" }
}
