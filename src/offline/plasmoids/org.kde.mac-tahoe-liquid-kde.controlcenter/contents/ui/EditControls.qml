// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
Page {
    id: view
    title: i18n("Edit Controls")
    property var preferences: null
    Repeater {
        model: [
            {key:"showWifi", label:i18n("Wi-Fi")},
            {key:"showBluetooth", label:i18n("Bluetooth")},
            {key:"showBattery", label:i18n("Battery")},
            {key:"showMedia", label:i18n("Now Playing")},
            {key:"showSharing", label:i18n("File Sharing")},
            {key:"showOverview", label:i18n("Overview")},
            {key:"showMirroring", label:i18n("Screen Mirroring")},
            {key:"showDarkMode", label:i18n("Dark Mode")},
            {key:"showScreenshot", label:i18n("Screenshot")},
            {key:"showFocus", label:i18n("Focus")},
            {key:"showNotifications", label:i18n("Notifications")},
            {key:"showSettings", label:i18n("Bluetooth Settings…")},
            {key:"showDisplay", label:i18n("Display")},
            {key:"showAudio", label:i18n("Sound")}
        ]
        delegate: QQC.CheckBox { font.family: "SF Pro Text"; font.pixelSize: 13;
            required property var modelData
            objectName: modelData.key
            text: modelData.label
            checked: !view.preferences || view.preferences[modelData.key] !== false
            onClicked: if (view.preferences) view.preferences[modelData.key] = checked
        }
    }
}
