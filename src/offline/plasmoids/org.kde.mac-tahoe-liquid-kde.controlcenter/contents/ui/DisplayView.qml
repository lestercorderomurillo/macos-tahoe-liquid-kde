// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "ControlStyle.js" as Style
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.brightnesscontrolplugin as Display
ColumnLayout {
    id: view
    // macOS Tahoe: title baseline row at 18 px, slider centred at 42 px of a 63 px tile.
    spacing: 5
    property var control: nativeControl
    property bool detailed: false
    signal detailsRequested()
    Display.ScreenBrightnessControl { id: nativeControl }
    QQC.AbstractButton { Layout.leftMargin: 16; Layout.topMargin: 11; padding: 0; text: i18n("Display"); onClicked: view.detailsRequested(); contentItem: ControlLabel { text: parent.text; font.pixelSize: Style.tileTitle; font.weight: Font.DemiBold } }
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
                Layout.leftMargin: 14; Layout.rightMargin: 14
                spacing: 7
                Kirigami.Icon { source: Style.symbol("mac-brightness-low"); roundToIconSize: false; isMask: true; color: Style.foreground(this, Window.window, "white"); implicitWidth: 15; implicitHeight: 15 }
                GlassSlider {
                objectName: "brightnessSlider"
                Layout.fillWidth: true
                Accessible.name: i18n("Brightness")
                from: 0; to: model.maxBrightness; value: model.brightness
                onMoved: view.control.setBrightness(model.displayName, Math.round(value))
                }
                Kirigami.Icon { source: Style.symbol("display-brightness"); roundToIconSize: false; isMask: true; color: Style.foreground(this, Window.window, "white"); implicitWidth: 18; implicitHeight: 18 }
            }
        }
    }
    Item { Layout.fillHeight: true }
    ControlLabel { visible: !view.control.isBrightnessAvailable && displays.count === 0; Layout.leftMargin: 16; font.pixelSize: Style.caption; opacity: 0.7; text: i18n("Brightness control unavailable") }
}
