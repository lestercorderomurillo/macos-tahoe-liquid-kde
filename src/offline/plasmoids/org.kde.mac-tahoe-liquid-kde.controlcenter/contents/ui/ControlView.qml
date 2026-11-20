// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQml.Models
import org.kde.mac.tahoe.launcher as Native
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
    // macOS Tahoe: four 63 px columns with 13 px gutters (291 px) inside a 10 px margin.
    // Extra 5 px right and 6 px top margins place the tiles where macOS draws them
    // relative to the menu bar button (16 px from the screen edge, 43 px from the top).
    // Transparent room left of and below the tiles for the backdrop shadow,
    // which the compositor can only draw inside this window. Input stays on the tiles.
    property int shadowMargin: 0
    implicitWidth: 316 + shadowMargin
    implicitHeight: 26 + shadowMargin + (section === "" ? grid.implicitHeight + 40 : detail.implicitHeight)
    ControlCommands { id: commands }
    // A press outside the tiles (the shadow margin) closes the panel, as on macOS.
    MouseArea {
        anchors.fill: parent; z: -1
        acceptedButtons: Qt.AllButtons; hoverEnabled: true
        onPressed: mouse => {
            const onGlass = view.surfaces.some(r => r.width && mouse.x >= r.x && mouse.x < r.x + r.width && mouse.y >= r.y && mouse.y < r.y + r.height);
            if (!onGlass) view.closeRequested();
        }
    }
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
    function surface(item) { if (!item.visible) return {}; return {x:item.x + (item === detail || item === edit ? 0 : grid.x), y:item.y + (item === detail || item === edit ? 0 : grid.y), width:item.width, height:item.height, radius:Math.floor(item.cornerRadius)}; }
    GridLayout {
        id: grid
        x: 10 + view.shadowMargin; y: 16
        width: 291
        visible: view.section === ""
        columns: 4
        columnSpacing: 13
        rowSpacing: 13
        ControlTile {
            id: wifi
            visible: view.showControl("showWifi")
            Layout.columnSpan: 2; Layout.fillWidth: false; Layout.preferredWidth: 139; Layout.minimumWidth: 0; Layout.preferredHeight: 63
            padding: 0
            contentItem: ControlAction {
                objectName: "connectionSummary"
                text: view.primaryConnection && !view.primaryConnection.wifi ? i18n("Network") : i18n("Wi-Fi")
                // macOS Tahoe keeps the Wi-Fi glyph on this tile whatever the link type.
                symbol: "network-wireless"
                active: !!view.primaryConnection
                subtitle: view.primaryConnection ? (view.primaryConnection.wifi ? view.primaryConnection.name : i18n("Connected")) : i18n("Not connected")
                disclosure: true
                onClicked: view.section = "WifiView.qml"
            }
        }
        ControlTile {
            id: media
            visible: view.showControl("showMedia")
            Layout.columnSpan: 2; Layout.rowSpan: 2; Layout.fillWidth: false; Layout.preferredWidth: 139; Layout.minimumWidth: 0; Layout.fillHeight: true
            cornerRadius: 24; padding: 13
            contentItem: MediaView {}
        }
        ControlTile {
            id: bluetooth
            visible: view.showControl("showBluetooth")
            Layout.columnSpan: 2; Layout.fillWidth: false; Layout.preferredWidth: 139; Layout.minimumWidth: 0; Layout.preferredHeight: 63; padding: 0
            contentItem: ControlAction {
                text: i18n("Bluetooth"); symbol: "preferences-system-bluetooth"
                subtitle: active ? i18n("On") : i18n("Off")
                active: Bluetooth.Manager.operational && !Bluetooth.Manager.bluetoothBlocked
                discToggles: Bluetooth.Manager.operational && Bluetooth.Manager.adapters.length > 0
                onDiscClicked: Bluetooth.Manager.bluetoothBlocked = !Bluetooth.Manager.bluetoothBlocked
                disclosure: true
                onClicked: view.section = "BluetoothView.qml"
            }
        }
        ControlTile {
            id: sharing
            visible: view.showControl("showSharing")
            Layout.columnSpan: 2; Layout.fillWidth: false; Layout.preferredWidth: 139; Layout.minimumWidth: 0; Layout.preferredHeight: 63; padding: 0
            contentItem: ControlAction { text: i18n("File Sharing"); symbol: "mac-airdrop-off"; iconDisc: true; serviceOff: true; onClicked: commands.run("sharing") }
        }
        ControlTile {
            id: overview
            visible: view.showControl("showOverview")
            Layout.fillWidth: false; Layout.preferredWidth: 63; Layout.minimumWidth: 0; Layout.preferredHeight: 63; padding: 0
            contentItem: ControlAction { text: i18n("Overview"); symbol: "mac-stage-manager"; compact: true; symbolSize: 32; onClicked: commands.run("overview") }
        }
        ControlTile {
            id: mirroring
            visible: view.showControl("showMirroring")
            Layout.fillWidth: false; Layout.preferredWidth: 63; Layout.minimumWidth: 0; Layout.preferredHeight: 63; padding: 0
            contentItem: ControlAction { text: i18n("Screen Mirroring"); symbol: "mac-mirroring"; compact: true; symbolSize: 28; onClicked: commands.run("display") }
        }
        ControlTile {
            id: darkMode
            visible: view.showControl("showDarkMode")
            Layout.fillWidth: false; Layout.preferredWidth: 63; Layout.minimumWidth: 0; Layout.preferredHeight: 63; padding: 0
            Native.AppearanceControl { id: appearance }
            contentItem: ControlAction {
                readonly property string mode: appearance.preference
                text: mode === "auto" ? i18n("Automatic") : mode === "light" ? i18n("Light") : i18n("Dark Mode")
                // macOS keeps the appearance glyph; the mode is in the tooltip.
                symbol: "mac-appearance"
                activeSymbolColor: "black"; symbolSize: 24
                compact: true
                active: !darkMode.lightMode
                onClicked: commands.run(mode === "light" ? "dark" : mode === "dark" ? "auto" : "light")
            }
        }
        ControlTile {
            id: screenshot
            visible: view.showControl("showScreenshot")
            Layout.fillWidth: false; Layout.preferredWidth: 63; Layout.minimumWidth: 0; Layout.preferredHeight: 63; padding: 0
            contentItem: ControlAction { text: i18n("Screenshot"); symbol: "mac-screenshot"; compact: true; symbolSize: 22; onClicked: { view.closeRequested(); commands.run("screenshot"); } }
        }
        ControlTile {
            id: focus
            visible: view.showControl("showFocus")
            Layout.columnSpan: 2; Layout.fillWidth: false; Layout.preferredWidth: 139; Layout.minimumWidth: 0; Layout.preferredHeight: 63; padding: 0
            contentItem: FocusSwitch {}
        }
        ControlTile {
            id: notifications
            visible: view.preferences && view.preferences.showNotifications === true
            Layout.fillWidth: false; Layout.preferredWidth: 63; Layout.minimumWidth: 0; Layout.preferredHeight: 63; padding: 0
            contentItem: ControlAction { text: i18n("Notifications"); symbol: "notifications"; compact: true; onClicked: view.section = "NotificationsView.qml" }
        }
        ControlTile {
            id: settings
            visible: view.preferences && view.preferences.showSettings === true
            Layout.fillWidth: false; Layout.preferredWidth: 63; Layout.minimumWidth: 0; Layout.preferredHeight: 63; padding: 0
            contentItem: ControlAction { text: i18n("Bluetooth Settings…"); symbol: "configure"; compact: true; onClicked: view.section = "BluetoothView.qml" }
        }
        ControlTile {
            id: battery
            objectName: "batteryTile"
            visible: view.showControl("showBattery") && view.batteryState.hasInternalBatteries
            Layout.fillWidth: false; Layout.preferredWidth: 63; Layout.minimumWidth: 0; Layout.preferredHeight: 63; padding: 0
            contentItem: ControlAction { text: i18n("Battery"); symbol: "battery"; compact: true; onClicked: view.section = "BatteryView.qml" }
        }
        ControlTile {
            id: display
            visible: view.showControl("showDisplay")
            Layout.columnSpan: 4; Layout.fillWidth: true; Layout.preferredHeight: 63; cornerRadius: 24; padding: 0
            contentItem: DisplayView { onDetailsRequested: view.section = "DisplayDetails.qml" }
        }
        ControlTile {
            id: audio
            visible: view.showControl("showAudio")
            Layout.columnSpan: 4; Layout.fillWidth: true; Layout.preferredHeight: 63; cornerRadius: 24; padding: 0
            contentItem: AudioView { onDetailsRequested: view.section = "AudioDetails.qml" }
        }
    }
    TextMetrics { id: editMetrics; text: i18n("Edit Controls"); font.family: Style.family; font.pixelSize: Style.tileTitle }
    ControlTile {
        id: edit
        // Center on whole logical pixels so the compositor can recover this capsule from its mask.
        width: Math.min(291, 2 * Math.ceil((editMetrics.width + 22) / 2)); height: 22
        x: grid.x + (grid.width - width) / 2; y: grid.y + grid.height + 17
        visible: view.section === ""
        padding: 0
        contentItem: QQC.AbstractButton {
            objectName: "editControlsButton"
            text: i18n("Edit Controls")
            padding: 0
            contentItem: ControlLabel {
                text: parent.text
                font.family: Style.family
                font.pixelSize: Style.tileTitle
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            onClicked: view.section = "EditControls.qml"
        }
    }
    ControlTile {
        id: detail
        x: 10 + view.shadowMargin; y: 16
        width: 291
        visible: view.section !== ""
        cornerRadius: 18; padding: 8
        contentItem: ColumnLayout {
            QQC.Button { visible: view.section !== "BluetoothView.qml" && view.section !== "WifiView.qml"; font.family: "SF Pro Text"; font.pixelSize: 13; text: i18n("Back"); icon.name: "go-previous"; flat: true; onClicked: view.section = "" }
            Loader { Layout.fillWidth: true; active: view.section !== ""; source: view.section; onLoaded: if (view.section === "EditControls.qml") item.preferences = view.preferences }
        }
    }
}
