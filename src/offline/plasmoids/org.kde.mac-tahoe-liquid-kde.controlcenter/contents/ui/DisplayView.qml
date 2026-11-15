// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.plasma.private.brightnesscontrolplugin as Display
ColumnLayout {
    id: view
    property var control: nativeControl
    Display.ScreenBrightnessControl { id: nativeControl }
    QQC.Label { text: i18n("Display"); font.bold: true }
    Repeater {
        model: view.control.displays
        delegate: ColumnLayout {
            required property var model
            Layout.fillWidth: true
            QQC.Label { visible: view.control.displays.rowCount() > 1; Layout.fillWidth: true; text: model.label || model.displayName; elide: Text.ElideRight }
            GlassSlider {
                objectName: "brightnessSlider"
                Layout.fillWidth: true
                Accessible.name: i18n("Brightness")
                from: 0; to: model.maxBrightness; value: model.brightness
                onMoved: view.control.setBrightness(model.displayName, Math.round(value))
            }
        }
    }
    QQC.Label { visible: !view.control.isBrightnessAvailable; text: i18n("Brightness control unavailable") }
}
