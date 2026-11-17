// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQml.Models
import "ControlStyle.js" as Style
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.plasma.networkmanagement as Network
import org.kde.bluezqt as Bluetooth
import org.kde.plasma.private.battery as Power
Item {
    id: view
    property string section: ""
    property var preferences: null
    function showControl(name) { return !preferences || preferences[name] !== false; }
    signal closeRequested()
    focus: true
    Keys.onEscapePressed: { if (section.length) section = ""; else closeRequested(); }
    implicitWidth: 360
    implicitHeight: 20 + (section === "" ? grid.implicitHeight + 42 : detail.implicitHeight)
    ControlCommands { id: commands }
    Network.EnabledConnections { id: wireless }
    Network.NetworkModel { id: nativeConnections }
    property var connections: nativeConnections
    Instantiator {
        id: activeConnections
        model: view.connections
        delegate: QtObject {
            required property var model
            readonly property bool physical: model.Type === Network.Enums.Wireless || model.Type === Network.Enums.Wired
            readonly property bool connected: model.ConnectionState === Network.Enums.Activated
            readonly property bool wifi: model.Type === Network.Enums.Wireless
            readonly property string name: model.Name || ""
        }
    }
    readonly property var primaryConnection: {
        for (let i = 0; i < activeConnections.count; ++i) {
            const connection = activeConnections.objectAt(i);
            if (connection && connection.physical && connection.connected)
                return {name: connection.name, wifi: connection.wifi};
        }
        return null;
    }
    property var batteryState: nativeBattery
    Power.BatteryControlModel { id: nativeBattery }
    readonly property var surfaces: section === "" ? [surface(wifi),surface(bluetooth),surface(sharing),surface(overview),surface(mirroring),surface(darkMode),surface(screenshot),surface(battery),surface(media),surface(focus),surface(notifications),surface(settings),surface(display),surface(audio),surface(edit)] : [surface(detail)]
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
            Layout.columnSpan: 2; Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 72
            padding: 10
            contentItem: ControlAction {
                objectName: "connectionSummary"
                text: view.primaryConnection && !view.primaryConnection.wifi ? i18n("Network") : i18n("Wi-Fi")
                symbol: view.primaryConnection && !view.primaryConnection.wifi ? "network-wired-symbolic" : "network-wireless"
                active: !!view.primaryConnection
                subtitle: view.primaryConnection ? (view.primaryConnection.wifi ? view.primaryConnection.name : i18n("Connected")) : i18n("Not connected")
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
            Layout.columnSpan: 2; Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 72; padding: 10
            contentItem: ControlAction {
                text: i18n("Bluetooth"); symbol: "preferences-system-bluetooth"
                subtitle: active ? i18n("On") : i18n("Off")
                active: Bluetooth.Manager.operational && !Bluetooth.Manager.bluetoothBlocked
                onClicked: {
                    if (Bluetooth.Manager.operational && Bluetooth.Manager.adapters.length > 0)
                        Bluetooth.Manager.bluetoothBlocked = !Bluetooth.Manager.bluetoothBlocked;
                    else view.section = "BluetoothView.qml";
                }
            }
        }
        ControlTile {
            id: sharing
            visible: view.showControl("showSharing")
            Layout.columnSpan: 2; Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 72; padding: 10
            contentItem: ControlAction { text: i18n("File Sharing"); symbol: "mac-airdrop-off"; iconDisc: true; onClicked: commands.run("sharing") }
        }
        ControlTile {
            id: overview
            visible: view.showControl("showOverview")
            Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 72; padding: 4
            contentItem: ControlAction { text: i18n("Overview"); symbol: "mac-stage-manager"; compact: true; onClicked: commands.run("overview") }
        }
        ControlTile {
            id: mirroring
            visible: view.showControl("showMirroring")
            Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 72; padding: 4
            contentItem: ControlAction { text: i18n("Screen Mirroring"); symbol: "mac-mirroring"; compact: true; onClicked: commands.run("display") }
        }
        ControlTile {
            id: darkMode
            visible: view.showControl("showDarkMode")
            Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 72; padding: 4
            contentItem: ControlAction { text: i18n("Dark Mode"); symbol: "mac-appearance"; activeSymbolColor: "black"; compact: true; active: !darkMode.lightMode; onClicked: commands.run(darkMode.lightMode ? "dark" : "light") }
        }
        ControlTile {
            id: screenshot
            visible: view.showControl("showScreenshot")
            Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 72; padding: 4
            contentItem: ControlAction { text: i18n("Screenshot"); symbol: "mac-screenshot"; compact: true; onClicked: { view.closeRequested(); commands.run("screenshot"); } }
        }
        ControlTile {
            id: focus
            visible: view.showControl("showFocus")
            Layout.columnSpan: 2; Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 72; padding: 10
            contentItem: FocusSwitch {}
        }
        ControlTile {
            id: notifications
            visible: view.preferences && view.preferences.showNotifications === true
            Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 72; padding: 4
            contentItem: ControlAction { text: i18n("Notifications"); symbol: "notifications"; compact: true; onClicked: view.section = "NotificationsView.qml" }
        }
        ControlTile {
            id: settings
            visible: view.preferences && view.preferences.showSettings === true
            Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 72; padding: 4
            contentItem: ControlAction { text: i18n("Bluetooth Settings…"); symbol: "configure"; compact: true; onClicked: view.section = "BluetoothView.qml" }
        }
        ControlTile {
            id: battery
            objectName: "batteryTile"
            visible: view.showControl("showBattery") && view.batteryState.hasInternalBatteries
            Layout.fillWidth: true; Layout.preferredWidth: 66; Layout.minimumWidth: 0; Layout.preferredHeight: 72; padding: 4
            contentItem: ControlAction { text: i18n("Battery"); symbol: "battery"; compact: true; onClicked: view.section = "BatteryView.qml" }
        }
        ControlTile {
            id: display
            visible: view.showControl("showDisplay")
            Layout.columnSpan: 4; Layout.fillWidth: true; Layout.minimumHeight: 64; cornerRadius: 24
            contentItem: DisplayView { onDetailsRequested: view.section = "DisplayDetails.qml" }
        }
        ControlTile {
            id: audio
            visible: view.showControl("showAudio")
            Layout.columnSpan: 4; Layout.fillWidth: true; Layout.minimumHeight: 64; cornerRadius: 24
            contentItem: AudioView { onDetailsRequested: view.section = "AudioDetails.qml" }
        }
    }
    TextMetrics { id: editMetrics; text: i18n("Edit Controls"); font.family: Style.family; font.pixelSize: Style.caption }
    ControlTile {
        id: edit
        width: Math.min(parent.width - 20, editMetrics.width + 28); height: 28
        x: (parent.width - width) / 2; y: grid.y + grid.height + 12
        visible: view.section === ""
        padding: 0
        contentItem: QQC.AbstractButton {
            objectName: "editControlsButton"
            text: i18n("Edit Controls")
            padding: 0
            contentItem: ControlLabel {
                text: parent.text
                font.family: Style.family
                font.pixelSize: Style.caption
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
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
            QQC.Button { font.family: "SF Pro Text"; font.pixelSize: 13; text: i18n("Back"); icon.name: "go-previous"; flat: true; onClicked: view.section = "" }
            Loader { Layout.fillWidth: true; active: view.section !== ""; source: view.section; onLoaded: if (view.section === "EditControls.qml") item.preferences = view.preferences }
        }
    }
}
