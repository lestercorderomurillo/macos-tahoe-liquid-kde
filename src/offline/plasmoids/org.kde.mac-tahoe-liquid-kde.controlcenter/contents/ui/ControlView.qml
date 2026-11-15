// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.plasma.networkmanagement as Network
import org.kde.bluezqt as Bluetooth
Item {
    id: view
    property string section: ""
    property var preferences: null
    function showControl(name) { return !preferences || preferences[name] !== false; }
    signal closeRequested()
    focus: true
    Keys.onEscapePressed: { if (section.length) section = ""; else closeRequested(); }
    implicitWidth: 320
    implicitHeight: 20 + (section === "" ? grid.implicitHeight + 42 : detail.implicitHeight)
    Network.EnabledConnections { id: wireless }
    Network.NetworkStatus { id: status }
    readonly property var surfaces: section === "" ? [surface(wifi),surface(bluetooth),surface(battery),surface(media),surface(focus),surface(notifications),surface(settings),surface(display),surface(audio),surface(edit)] : [surface(detail)]
    function surface(item) { if (!item.visible) return {}; return {x:item.x + (item === detail || item === edit ? 0 : grid.x), y:item.y + (item === detail || item === edit ? 0 : grid.y), width:item.width, height:item.height, radius:item.cornerRadius}; }
    GridLayout {
        id: grid
        x: 10; y: 10
        width: parent.width - 20
        visible: view.section === ""
        columns: 4
        columnSpacing: 12
        rowSpacing: 12
        ControlTile {
            id: wifi
            visible: view.showControl("showWifi")
            Layout.columnSpan: 2; Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 64
            padding: 10
            contentItem: ControlAction {
                text: i18n("Wi-Fi")
                symbol: "network-wireless"
                active: wireless.wirelessEnabled
                subtitle: wireless.wirelessEnabled ? status.activeConnections || i18n("Not connected") : i18n("Wi-Fi is off")
                onClicked: view.section = "WifiView.qml"
            }
        }
        ControlTile {
            id: media
            visible: view.showControl("showMedia")
            Layout.columnSpan: 2; Layout.rowSpan: 2; Layout.fillWidth: true; Layout.preferredWidth: 144; Layout.minimumWidth: 0; Layout.fillHeight: true
            cornerRadius: 28
            contentItem: MediaView {}
        }
        ControlTile {
            id: bluetooth
            visible: view.showControl("showBluetooth")
            Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 64; padding: 4
            contentItem: ControlAction {
                text: i18n("Bluetooth"); symbol: "preferences-system-bluetooth"; compact: true
                active: Bluetooth.Manager.operational && !Bluetooth.Manager.bluetoothBlocked
                enabled: Bluetooth.Manager.operational && Bluetooth.Manager.adapters.length > 0
                onClicked: Bluetooth.Manager.bluetoothBlocked = !Bluetooth.Manager.bluetoothBlocked
            }
        }
        ControlTile {
            id: battery
            visible: view.showControl("showBattery")
            Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 64; padding: 4
            contentItem: ControlAction { text: i18n("Battery"); symbol: "battery"; compact: true; onClicked: view.section = "BatteryView.qml" }
        }
        ControlTile {
            id: focus
            visible: view.showControl("showFocus")
            Layout.columnSpan: 2; Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 64; padding: 10
            contentItem: FocusSwitch {}
        }
        ControlTile {
            id: notifications
            visible: view.showControl("showNotifications")
            Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 64; padding: 4
            contentItem: ControlAction { text: i18n("Notifications"); symbol: "notifications"; compact: true; onClicked: view.section = "NotificationsView.qml" }
        }
        ControlTile {
            id: settings
            visible: view.showControl("showSettings")
            Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 64; padding: 4
            contentItem: ControlAction { text: i18n("Bluetooth Settings…"); symbol: "configure"; compact: true; onClicked: view.section = "BluetoothView.qml" }
        }
        ControlTile {
            id: display
            visible: view.showControl("showDisplay")
            Layout.columnSpan: 4; Layout.fillWidth: true; Layout.minimumHeight: 64; cornerRadius: 24
            contentItem: DisplayView {}
        }
        ControlTile {
            id: audio
            visible: view.showControl("showAudio")
            Layout.columnSpan: 4; Layout.fillWidth: true; Layout.minimumHeight: 64; cornerRadius: 24
            contentItem: AudioView {}
        }
    }
    ControlTile {
        id: edit
        width: 110; height: 28
        x: (parent.width - width) / 2; y: grid.y + grid.height + 12
        visible: view.section === ""
        padding: 0
        contentItem: QQC.Button {
            flat: true
            text: i18n("Edit Controls")
            font.pixelSize: 11
            onClicked: view.section = "EditControls.qml"
        }
    }
    ControlTile {
        id: detail
        x: 10; y: 10
        width: parent.width - 20
        visible: view.section !== ""
        cornerRadius: 24
        contentItem: ColumnLayout {
            QQC.Button { text: i18n("Back"); icon.name: "go-previous"; flat: true; onClicked: view.section = "" }
            Loader { Layout.fillWidth: true; active: view.section !== ""; source: view.section; onLoaded: if (view.section === "EditControls.qml") item.preferences = view.preferences }
        }
    }
}
