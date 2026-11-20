// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.plasma.networkmanagement as Network
Page {
    id: view
    title: ""
    spacing: 4
    Layout.preferredWidth: 280
    property var wireless: enabledConnections
    property var devices: nativeDevices
    property var connectionIcon: nativeIcon
    property var handler: nativeHandler
    property var connections: available
    property string error: ""
    property bool otherNetworksExpanded: false
    readonly property bool wirelessAvailable: devices.wirelessDeviceAvailable && wireless.wirelessHwEnabled && wireless.wirelessEnabled
    readonly property bool lightMode: Kirigami.Theme.textColor.r * 0.2126 + Kirigami.Theme.textColor.g * 0.7152 + Kirigami.Theme.textColor.b * 0.0722 < 0.5
    Network.AvailableDevices { id: nativeDevices }
    Network.EnabledConnections { id: enabledConnections }
    Network.ConnectionIcon { id: nativeIcon }
    Network.Handler {
        id: nativeHandler
        onConnectionActivationFailed: (path, message) => view.error = message
    }
    Network.NetworkModel { id: networks }
    Network.AppletProxyModel { id: available; sourceModel: networks }
    function activate(network) {
        error = "";
        if (network.ConnectionState === Network.Enums.Activated)
            handler.deactivateConnection(network.ConnectionPath, network.DevicePath);
        else if (network.ConnectionPath)
            handler.activateConnection(network.ConnectionPath, network.DevicePath, network.SpecificPath);
        else handler.addAndActivateConnection(network.DevicePath, network.SpecificPath);
    }
    MacSwitchHeader {
        id: toggle
        objectName: "wirelessToggle"
        text: i18n("Wi-Fi")
        checked: view.wireless.wirelessEnabled
        enabled: view.devices.wirelessDeviceAvailable && view.wireless.wirelessHwEnabled
        onClicked: view.handler.enableWireless(!view.wireless.wirelessEnabled)
    }
    StatusMenuDivider {}
    ControlLabel {
        Layout.fillWidth: true; Layout.leftMargin: 6; Layout.rightMargin: 6; Layout.topMargin: 4; Layout.bottomMargin: 4
        visible: !view.wirelessAvailable
        wrapMode: Text.WordWrap
        text: !view.devices.wirelessDeviceAvailable ? i18n("No Wi-Fi adapter")
            : !view.wireless.wirelessHwEnabled ? i18n("Wi-Fi is blocked by the hardware switch") : i18n("Wi-Fi is off")
        opacity: 0.65
    }
    // Wired links have no switch on macOS; list the active ones as known networks.
    Repeater {
        id: wiredRepeater
        model: view.connections
        delegate: StatusMenuRow {
            objectName: "wiredRow"
            required property var model
            Layout.fillWidth: true
            visible: model.Type === Network.Enums.Wired && !!model.ConnectionPath
            text: model.Name || ""
            symbol: "network-wired-symbolic"
            selected: model.ConnectionState === Network.Enums.Activated
            busy: model.ConnectionState === Network.Enums.Activating
            enabled: !busy
            onClicked: view.activate(model)
        }
    }
    StatusMenuDivider {}
    QQC.ScrollView {
        id: networkScroll
        padding: 0
        contentWidth: availableWidth
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(networksColumn.implicitHeight, 300)
        visible: view.wirelessAvailable
        clip: true
        QQC.ScrollBar.horizontal.policy: QQC.ScrollBar.AlwaysOff
        ColumnLayout {
            id: networksColumn
            width: networkScroll.availableWidth
            spacing: 4
            ControlLabel { text: i18n("Known Networks"); font.weight: Font.DemiBold; font.pixelSize: 12; opacity: 0.6; Layout.leftMargin: 6; Layout.rightMargin: 6; Layout.topMargin: 4; Layout.bottomMargin: 4 }
            Repeater {
                model: view.connections
                delegate: StatusMenuRow {
                    objectName: "networkRow"
                    required property var model
                    Layout.fillWidth: true
                    visible: model.Type === Network.Enums.Wireless && !!model.ConnectionPath
                    text: model.Name || ""
                    symbol: "network-wireless"
                    selected: model.ConnectionState === Network.Enums.Activated
                    busy: model.ConnectionState === Network.Enums.Activating
                    secured: model.SecurityType !== undefined && model.SecurityType !== Network.Enums.NoneSecurity
                    enabled: view.wirelessAvailable && !busy
                    onClicked: view.activate(model)
                }
            }
            StatusMenuDivider {}
            StatusMenuRow {
                objectName: "otherNetworks"
                Layout.fillWidth: true
                text: i18n("Other Networks")
                disclosure: true
                opened: view.otherNetworksExpanded
                onClicked: {
                    view.otherNetworksExpanded = !view.otherNetworksExpanded;
                    if (view.otherNetworksExpanded && !view.handler.scanning) view.handler.requestScan();
                }
            }
            Repeater {
                model: view.connections
                delegate: StatusMenuRow {
                    objectName: "otherNetworkRow"
                    required property var model
                    Layout.fillWidth: true
                    visible: view.otherNetworksExpanded && model.Type === Network.Enums.Wireless && !model.ConnectionPath
                    text: model.Name || ""
                    symbol: "network-wireless"
                    busy: model.ConnectionState === Network.Enums.Activating
                    secured: model.SecurityType !== undefined && model.SecurityType !== Network.Enums.NoneSecurity
                    enabled: view.wirelessAvailable && !busy
                    onClicked: view.activate(model)
                }
            }
            StatusMenuRow {
                objectName: "scanNetworks"
                Layout.fillWidth: true
                visible: view.otherNetworksExpanded
                text: view.handler.scanning ? i18n("Scanning…") : i18n("Scan for Networks")
                enabled: view.wirelessAvailable && !view.handler.scanning
                onClicked: view.handler.requestScan()
            }
        }
    }
    ControlLabel { Layout.fillWidth: true; Layout.leftMargin: 6; Layout.rightMargin: 6; Layout.topMargin: 4; Layout.bottomMargin: 4; visible: view.error.length > 0; text: view.error; textFormat: Text.PlainText; wrapMode: Text.WordWrap }
    StatusMenuDivider {}
    SettingsLink {
        Layout.fillWidth: true
        text: i18n("Wi-Fi Settings…"); module: "kcm_networkmanagement"
        implicitHeight: 36
        icon.name: ""
        leftPadding: 6; rightPadding: 6
        background: Rectangle { radius: 8; color: Kirigami.Theme.textColor; opacity: parent.hovered || parent.activeFocus ? 0.10 : 0 }
        contentItem: ControlLabel { text: parent.text; verticalAlignment: Text.AlignVCenter }
    }
}
