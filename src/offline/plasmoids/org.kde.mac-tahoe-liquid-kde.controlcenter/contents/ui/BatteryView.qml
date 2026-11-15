// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.battery as Power
import org.kde.plasma.private.batterymonitor as Profiles
Page {
    id: view
    title: i18n("Battery")
    property var battery: nativeBattery
    property var profiles: nativeProfiles
    Power.BatteryControlModel { id: nativeBattery }
    Profiles.PowerProfilesControl { id: nativeProfiles }
    ControlLabel {
        objectName: "batteryPercent"
        Layout.fillWidth: true
        text: view.battery.hasInternalBatteries ? i18n("%1%", view.battery.percent) : i18n("No internal battery")
        font: Kirigami.Theme.defaultFont
        Accessible.name: text
    }
    QQC.ProgressBar { Layout.fillWidth: true; visible: view.battery.hasInternalBatteries; from: 0; to: 100; value: view.battery.percent }
    ControlLabel {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: !view.battery.hasInternalBatteries ? i18n("Battery information will appear when a battery is available.")
            : view.battery.state === Power.BatteryControlModel.Charging ? i18n("Charging")
            : view.battery.state === Power.BatteryControlModel.FullyCharged ? i18n("Fully charged")
            : view.battery.pluggedIn ? i18n("Connected to power") : i18n("On battery power")
    }
    Repeater {
        model: view.battery
        delegate: ControlLabel {
            required property var model
            visible: !model.IsPowerSupply
            text: i18n("%1 — %2%", model.PrettyName, model.Percent)
            Layout.fillWidth: true
            elide: Text.ElideRight
        }
    }
    ControlLabel { text: i18n("Energy mode"); visible: view.profiles.isPowerProfileDaemonInstalled }
    QQC.ComboBox { font.family: "SF Pro Text"; font.pixelSize: 13;
        objectName: "powerProfile"
        Layout.fillWidth: true
        visible: view.profiles.isPowerProfileDaemonInstalled
        model: view.profiles.profiles
        currentIndex: view.profiles.profiles.indexOf(view.profiles.activeProfile)
        displayText: currentText === "power-saver" ? i18n("Power saver") : currentText === "performance" ? i18n("Performance") : currentText === "balanced" ? i18n("Balanced") : currentText
        onActivated: view.profiles.setProfile(currentText)
        Accessible.name: i18n("Energy mode")
    }
    ControlLabel { Layout.fillWidth: true; visible: text.length > 0; text: view.profiles.profileError; wrapMode: Text.WordWrap }
    SettingsLink { text: i18n("Energy Settings…"); module: "kcm_powerdevilprofilesconfig" }
}
