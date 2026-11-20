// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.battery as Power
import org.kde.plasma.private.batterymonitor as Profiles
import "ControlStyle.js" as Style
Page {
    id: view
    title: ""
    spacing: 4
    Layout.preferredWidth: 280
    property var battery: nativeBattery
    property var profiles: nativeProfiles
    readonly property bool hasProfiles: profiles.isPowerProfileDaemonInstalled && profiles.profiles.length > 0
    Power.BatteryControlModel { id: nativeBattery }
    Profiles.PowerProfilesControl { id: nativeProfiles }
    function profileLabel(profile) {
        return profile === "power-saver" ? i18n("Low Power") : profile === "performance" ? i18n("High Power") : profile === "balanced" ? i18n("Automatic") : profile;
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 6; Layout.rightMargin: 6; Layout.topMargin: 4; Layout.bottomMargin: 4
        ControlLabel { text: i18n("Battery"); font.weight: Font.DemiBold; Layout.fillWidth: true }
        ControlLabel {
            objectName: "batteryPercent"
            text: view.battery.hasInternalBatteries ? i18n("%1%", view.battery.percent) : i18n("No internal battery")
            opacity: 0.65
            Accessible.name: text
        }
    }
    ControlLabel {
        objectName: "batterySource"
        Layout.fillWidth: true; Layout.leftMargin: 6; Layout.rightMargin: 6; Layout.topMargin: 4; Layout.bottomMargin: 4
        wrapMode: Text.WordWrap
        font.pixelSize: 12; opacity: 0.65
        text: !view.battery.hasInternalBatteries ? i18n("Connect a battery to see its status.")
            : view.battery.pluggedIn ? i18n("Power Source: Power Adapter") : i18n("Power Source: Battery")
    }
    ControlLabel {
        Layout.fillWidth: true; Layout.leftMargin: 6; Layout.rightMargin: 6; Layout.bottomMargin: 6
        visible: view.battery.hasInternalBatteries && view.battery.pluggedIn
        font.pixelSize: 12; opacity: 0.65
        text: view.battery.state === Power.BatteryControlModel.Charging ? i18n("Charging")
            : view.battery.state === Power.BatteryControlModel.FullyCharged ? i18n("Fully charged") : i18n("Connected to power")
    }
    StatusMenuDivider { visible: view.hasProfiles }
    ControlLabel { text: i18n("Energy Mode"); font.pixelSize: 12; font.weight: Font.DemiBold; opacity: 0.6; Layout.leftMargin: 6; Layout.rightMargin: 6; Layout.topMargin: 4; Layout.bottomMargin: 4; visible: view.hasProfiles }
    QQC.ComboBox {
        id: profile
        objectName: "powerProfile"
        Layout.fillWidth: true
        implicitHeight: 36
        visible: view.hasProfiles
        model: view.profiles.profiles
        currentIndex: view.profiles.profiles.indexOf(view.profiles.activeProfile)
        displayText: currentIndex >= 0 ? view.profileLabel(currentText) : i18n("Energy mode")
        onActivated: view.profiles.setProfile(currentText)
        Accessible.name: i18n("Energy mode")
        leftPadding: 6; rightPadding: 6
        background: Item {
            Rectangle { anchors.fill: parent; radius: 8; color: Kirigami.Theme.textColor; opacity: profile.hovered || profile.activeFocus ? 0.10 : 0 }
            Rectangle {
                x: profile.leftPadding; y: (parent.height - height) / 2
                width: 26; height: 26; radius: 13; color: "#008aff"
                Kirigami.Icon { anchors.centerIn: parent; width: 18; height: 18; source: Style.symbol("battery"); isMask: true; color: "white" }
            }
        }
        indicator: Kirigami.Icon {
            x: profile.width - width - profile.rightPadding
            y: (profile.height - height) / 2
            source: Style.symbol("mac-menu-chevron"); isMask: true; color: Kirigami.Theme.textColor
            width: 12; height: 12; opacity: 0.65
        }
        contentItem: ControlLabel {
            text: profile.displayText
            leftPadding: 34; rightPadding: 20
            verticalAlignment: Text.AlignVCenter
        }
        delegate: QQC.ItemDelegate {
            required property string modelData
            width: profile.width
            text: view.profileLabel(modelData)
            font.family: Style.family; font.pixelSize: Style.body
            highlighted: profile.currentText === modelData
        }
    }
    ControlLabel { Layout.fillWidth: true; Layout.leftMargin: 6; Layout.rightMargin: 6; Layout.topMargin: 4; Layout.bottomMargin: 4; visible: text.length > 0; text: view.profiles.profileError; textFormat: Text.PlainText; wrapMode: Text.WordWrap }
    Repeater {
        model: view.battery
        delegate: ControlLabel {
            required property var model
            objectName: "peripheralBattery"
            visible: model.IsPowerSupply === false && model.PrettyName !== undefined && model.Percent !== undefined
            text: visible ? i18n("%1 — %2%", model.PrettyName, model.Percent) : ""
            Layout.fillWidth: true; Layout.leftMargin: 6; Layout.rightMargin: 6; Layout.topMargin: 4; Layout.bottomMargin: 4
            elide: Text.ElideRight
        }
    }
    StatusMenuDivider {}
    SettingsLink {
        Layout.fillWidth: true
        text: i18n("Battery Settings…"); module: "kcm_powerdevilprofilesconfig"
        implicitHeight: 36
        icon.name: ""
        leftPadding: 6; rightPadding: 6
        background: Rectangle { radius: 8; color: Kirigami.Theme.textColor; opacity: parent.hovered || parent.activeFocus ? 0.10 : 0 }
        contentItem: ControlLabel { text: parent.text; verticalAlignment: Text.AlignVCenter }
    }
}
