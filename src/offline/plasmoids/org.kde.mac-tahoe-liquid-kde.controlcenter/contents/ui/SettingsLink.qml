// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls as QQC
import org.kde.plasma.plasma5support as Support
QQC.Button { font.family: "SF Pro Text"; font.pixelSize: 13;
    id: button
    property string module
    flat: true
    icon.name: "configure"
    onClicked: {
        const allowed = ["kcm_networkmanagement", "kcm_bluetooth", "kcm_pulseaudio", "kcm_powerdevilprofilesconfig", "kcm_notifications", "kcm_kscreen"];
        if (allowed.indexOf(module) >= 0) runner.connectSource("systemsettings " + module);
    }
    Support.DataSource {
        id: runner
        engine: "executable"
        onNewData: (sourceName, data) => disconnectSource(sourceName)
    }
}
