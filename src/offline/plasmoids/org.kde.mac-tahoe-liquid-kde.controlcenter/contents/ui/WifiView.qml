// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.plasma.networkmanagement as Network
Page {
    id: view
    title: ""
    property var wireless: enabledConnections
    property var devices: nativeDevices
    property var connectionIcon: nativeIcon
    property var handler: nativeHandler
    property var connections: available
    property string error: ""
    Network.AvailableDevices { id: nativeDevices }
    Network.EnabledConnections { id: enabledConnections }
    Network.ConnectionIcon { id: nativeIcon }
    Network.NetworkStatus { id: status }
    Network.Handler {
        id: nativeHandler
        onConnectionActivationFailed: (path, message) => view.error = message
    }
    Network.NetworkModel { id: networks }
    Network.AppletProxyModel { id: available; sourceModel: networks }
    QQC.Switch { font.family: "SF Pro Text"; font.pixelSize: 13;
        objectName: "wirelessToggle"
        text: i18n("Wi-Fi")
        checked: view.wireless.wirelessEnabled
        enabled: view.devices.wirelessDeviceAvailable && view.wireless.wirelessHwEnabled
        onClicked: view.handler.enableWireless(!view.wireless.wirelessEnabled)
    }
    ControlLabel {
        Layout.fillWidth: true; wrapMode: Text.WordWrap
        text: !view.devices.wirelessDeviceAvailable ? i18n("No Wi-Fi adapter")
            : !view.wireless.wirelessHwEnabled ? i18n("Wi-Fi is blocked by the hardware switch")
            : !view.wireless.wirelessEnabled ? i18n("Wi-Fi is off") : status.activeConnections || i18n("Not connected")
    }
    QQC.ScrollView {
        Layout.fillWidth: true
        Layout.preferredHeight: Kirigami.Units.gridUnit * 12
        visible: view.devices.wirelessDeviceAvailable && view.wireless.wirelessEnabled
        clip: true
        ListView {
            id: list
            model: view.connections
            delegate: QQC.ItemDelegate { font.family: "SF Pro Text"; font.pixelSize: 13;
                objectName: "networkRow"
                required property var model
                width: ListView.view.width
                visible: model.Type === Network.Enums.Wireless
                height: visible ? implicitHeight : 0
                text: model.Name || ""
                icon.name: model.ConnectionIcon || "network-wireless"
                onClicked: {
                    view.error = "";
                    if (model.ConnectionState === Network.Enums.Activated)
                        view.handler.deactivateConnection(model.ConnectionPath, model.DevicePath);
                    else if (model.ConnectionPath)
                        view.handler.activateConnection(model.ConnectionPath, model.DevicePath, model.SpecificPath);
                    else view.handler.addAndActivateConnection(model.DevicePath, model.SpecificPath);
                }
            }
        }
    }
    ControlLabel { Layout.fillWidth: true; visible: view.error.length > 0; text: view.error; wrapMode: Text.WordWrap }
    QQC.Button { font.family: "SF Pro Text"; font.pixelSize: 13; text: view.handler.scanning ? i18n("Scanning…") : i18n("Scan for Networks"); enabled: view.devices.wirelessDeviceAvailable && view.wireless.wirelessHwEnabled && view.wireless.wirelessEnabled && !view.handler.scanning; onClicked: view.handler.requestScan() }
    SettingsLink { text: i18n("Network Settings…"); module: "kcm_networkmanagement" }
}
