// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls as QQC
import org.kde.notificationmanager as Notifications
ControlAction {
    id: control
    text: i18n("Focus")
    symbol: "weather-clear-night"
    iconDisc: true
    checkable: true
    active: checked
    subtitle: checked ? i18n("Do Not Disturb") : ""
    property var settings: nativeSettings
    Notifications.Settings { id: nativeSettings }
    property date now: new Date()
    Timer { interval: 1000; running: control.visible; repeat: true; onTriggered: control.now = new Date() }
    checked: control.settings.notificationsInhibitedUntil > now || control.settings.notificationsInhibitedByApplication
    enabled: !control.settings.notificationsInhibitedByApplication
    onClicked: {
        control.settings.notificationsInhibitedUntil = checked ? new Date(Date.now() + 3600000) : new Date(0);
        control.settings.save();
    }
    QQC.ToolTip.visible: hovered
    QQC.ToolTip.text: control.settings.notificationsInhibitedByApplication ? i18n("Controlled by another application") : i18n("Pause notifications for one hour")
}
