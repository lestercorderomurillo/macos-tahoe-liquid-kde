// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "ControlStyle.js" as Style
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.volume as Audio
ColumnLayout {
    id: view
    spacing: 5
    property bool detailed: false
    signal detailsRequested()
    property var sink: Audio.PreferredDevice.sink
    ControlLabel { Layout.leftMargin: 16; Layout.topMargin: 11; text: i18n("Sound"); font.pixelSize: Style.tileTitle; font.weight: Font.DemiBold }
    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 12; Layout.rightMargin: 13
        spacing: 6
        ControlIconButton { font.family: "SF Pro Text"; font.pixelSize: 13;
            icon.source: Style.symbol(view.sink && view.sink.muted ? "audio-volume-muted" : "mac-speaker-low")
            icon.width: 16; icon.height: 16; padding: 0; implicitWidth: 22; implicitHeight: 22
            objectName: "muteButton"
            text: i18n("Mute sound"); Accessible.name: text
            display: QQC.AbstractButton.IconOnly
            checkable: true; checked: view.sink ? view.sink.muted : false; enabled: !!view.sink
            onClicked: view.sink.muted = !view.sink.muted
        }
        GlassSlider {
            Layout.fillWidth: true
            objectName: "volumeSlider"
            Accessible.name: i18n("Volume")
            from: 0; to: Audio.PulseAudio.NormalVolume
            value: view.sink ? view.sink.volume : 0; enabled: !!view.sink
            onMoved: {
                if (!view.sink) return;
                view.sink.volume = Math.round(value);
                view.sink.muted = value === 0;
            }
        }
        Kirigami.Icon { source: Style.symbol("audio-volume-high"); roundToIconSize: false; isMask: true; color: Style.foreground(this, Window.window, Kirigami.Theme.textColor); implicitWidth: 22; implicitHeight: 22 }
        ControlIconButton {
            objectName: "audioOutputs"
            implicitWidth: 26; implicitHeight: 26; padding: 4
            background: Rectangle { radius: width / 2; color: Qt.rgba(1,1,1,0.18) }
            icon.source: Style.symbol("mac-airplay")
            text: i18n("Audio outputs"); Accessible.name: text
            display: QQC.AbstractButton.IconOnly
            onClicked: view.detailsRequested()
        }
    }
    ControlLabel { visible: view.detailed; Layout.fillWidth: true; Layout.leftMargin: 16; font.pixelSize: Style.caption; opacity: 0.7; text: view.sink ? view.sink.description : i18n("No audio output"); elide: Text.ElideRight }
    Item { Layout.fillHeight: true }
}
