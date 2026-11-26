// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.bluezqt as Bluetooth
// macOS Tahoe Bluetooth module: switch, paired devices (blue when connected,
// battery level on the right) and the settings link.
ColumnLayout {
    id: view
    spacing: 2
    Layout.preferredWidth: 280
    readonly property bool powered: Bluetooth.Manager.bluetoothOperational && !Bluetooth.Manager.bluetoothBlocked
    readonly property bool lightMode: Kirigami.Theme.textColor.r * 0.2126 + Kirigami.Theme.textColor.g * 0.7152 + Kirigami.Theme.textColor.b * 0.0722 < 0.5
    function deviceSymbol(icon) {
        if (/headset|headphone|audio-head/.test(icon)) return "audio-headphones-symbolic";
        if (/phone/.test(icon)) return "phone-symbolic";
        if (/mouse/.test(icon)) return "input-mouse-symbolic";
        if (icon === "input-tablet" || icon === "printer") return icon + "-symbolic";
        if (/keyboard/.test(icon)) return "input-keyboard-symbolic";
        if (/speaker|audio-card|multimedia/.test(icon)) return "audio-speakers-symbolic";
        return icon || "preferences-system-bluetooth";
    }
    MacSwitchHeader {
        objectName: "bluetoothToggle"
        text: i18n("Bluetooth")
        checked: view.powered
        enabled: Bluetooth.Manager.operational && Bluetooth.Manager.adapters.length > 0
        onClicked: {
            const enable = !view.powered;
            if (enable)
                Bluetooth.Manager.bluetoothBlocked = false;
            for (const adapter of Bluetooth.Manager.adapters)
                adapter.powered = enable;
            if (!enable)
                Bluetooth.Manager.bluetoothBlocked = true;
        }
    }
    StatusMenuDivider {}
    ControlLabel {
        Layout.fillWidth: true; Layout.leftMargin: 6; Layout.rightMargin: 6; Layout.topMargin: 2; Layout.bottomMargin: 4
        visible: !view.powered
        wrapMode: Text.WordWrap
        opacity: 0.65
        text: !Bluetooth.Manager.operational || Bluetooth.Manager.adapters.length === 0 ? i18n("No Bluetooth adapter") : i18n("Bluetooth is off")
    }
    Repeater {
        model: Bluetooth.DevicesModel { id: devices }
        delegate: StatusMenuRow {
            objectName: "bluetoothDeviceRow"
            required property var model
            readonly property var device: model.Device
            Layout.fillWidth: true
            visible: view.powered && !!device && device.paired
            text: device ? device.name : ""
            symbol: view.deviceSymbol(device ? device.icon : "")
            selected: !!device && device.connected
            detail: device && device.connected && device.battery ? device.battery.percentage + " %" : ""
            busy: false
            onClicked: { if (device.connected) device.disconnectFromDevice(); else device.connectToDevice(); }
        }
    }
    StatusMenuDivider {}
    SettingsLink {
        Layout.fillWidth: true
        text: i18n("Bluetooth Settings…"); module: "kcm_bluetooth"
        implicitHeight: 32
        icon.name: ""
        leftPadding: 6; rightPadding: 6
        background: Rectangle { radius: 8; color: Kirigami.Theme.textColor; opacity: parent.hovered || parent.activeFocus ? 0.10 : 0 }
        contentItem: ControlLabel { text: parent.text; verticalAlignment: Text.AlignVCenter }
    }
}
