// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "ControlStyle.js" as Style
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.brightnesscontrolplugin as Display
ColumnLayout {
    id: view
    property var control: nativeControl
    property bool detailed: false
    signal detailsRequested()
    Display.ScreenBrightnessControl { id: nativeControl }
    QQC.AbstractButton { text: i18n("Display"); onClicked: view.detailsRequested(); contentItem: ControlLabel { text: parent.text; font.weight: Font.DemiBold } }
    Repeater {
        id: displays
        model: view.control.displays
        delegate: ColumnLayout {
            required property var model
            required property int index
            visible: view.detailed || index === 0
            Layout.fillWidth: true
            ControlLabel { objectName: "displayLabel"; visible: view.detailed && displays.count > 1; Layout.fillWidth: true; text: model.label || model.displayName; elide: Text.ElideRight }
            RowLayout {
                Layout.fillWidth: true
                Kirigami.Icon { source: Style.symbol("mac-brightness-low"); implicitWidth: 16; implicitHeight: 16 }
                GlassSlider {
                objectName: "brightnessSlider"
                Layout.fillWidth: true
                Accessible.name: i18n("Brightness")
                from: 0; to: model.maxBrightness; value: model.brightness
                onMoved: view.control.setBrightness(model.displayName, Math.round(value))
                }
                Kirigami.Icon { source: Style.symbol("display-brightness"); implicitWidth: 20; implicitHeight: 20 }
            }
        }
    }
    ControlLabel { visible: !view.control.isBrightnessAvailable; text: i18n("Brightness control unavailable") }
}
