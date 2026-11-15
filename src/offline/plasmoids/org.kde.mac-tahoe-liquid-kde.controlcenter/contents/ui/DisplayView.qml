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
    Display.ScreenBrightnessControl { id: nativeControl }
    ControlLabel { text: i18n("Display"); font.weight: Font.DemiBold }
    Repeater {
        model: view.control.displays
        delegate: ColumnLayout {
            required property var model
            Layout.fillWidth: true
            ControlLabel { visible: view.control.displays.rowCount() > 1; Layout.fillWidth: true; text: model.label || model.displayName; elide: Text.ElideRight }
            RowLayout {
                Layout.fillWidth: true
                Kirigami.Icon { source: Style.symbol("display-brightness"); implicitWidth: 14; implicitHeight: 14 }
                GlassSlider {
                objectName: "brightnessSlider"
                Layout.fillWidth: true
                Accessible.name: i18n("Brightness")
                from: 0; to: model.maxBrightness; value: model.brightness
                onMoved: view.control.setBrightness(model.displayName, Math.round(value))
                }
                Kirigami.Icon { source: Style.symbol("display-brightness"); implicitWidth: 18; implicitHeight: 18 }
            }
        }
    }
    ControlLabel { visible: !view.control.isBrightnessAvailable; text: i18n("Brightness control unavailable") }
}
