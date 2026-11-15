// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.bluezqt as Bluetooth
ColumnLayout {
    QQC.Switch { font.family: "SF Pro Text"; font.pixelSize: 13;
        text: i18n("Bluetooth")
        checked: Bluetooth.Manager.operational && !Bluetooth.Manager.bluetoothBlocked
        enabled: Bluetooth.Manager.operational && Bluetooth.Manager.adapters.length > 0
        onClicked: Bluetooth.Manager.bluetoothBlocked = !Bluetooth.Manager.bluetoothBlocked
    }
    SettingsLink { text: i18n("Bluetooth Settings…"); module: "kcm_bluetooth" }
}
