// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "ControlStyle.js" as Style
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.volume as Audio
ColumnLayout {
    id: view
    property bool detailed: false
    signal detailsRequested()
    property var sink: Audio.PreferredDevice.sink
    ControlLabel { text: i18n("Sound"); font.weight: Font.DemiBold }
    RowLayout {
        ControlIconButton { font.family: "SF Pro Text"; font.pixelSize: 13;
            icon.color: Kirigami.Theme.textColor; icon.source: Style.symbol(view.sink && view.sink.muted ? "audio-volume-muted" : "mac-speaker-low")
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
        Kirigami.Icon { source: Style.symbol("audio-volume-high"); implicitWidth: 22; implicitHeight: 22 }
        ControlIconButton {
            objectName: "audioOutputs"
            implicitWidth: 28; implicitHeight: 28; padding: 4
            background: Rectangle { radius: width / 2; color: Qt.rgba(1,1,1,0.18) }
            icon.source: Style.symbol("mac-airplay"); icon.color: Kirigami.Theme.textColor
            text: i18n("Audio outputs"); Accessible.name: text
            display: QQC.AbstractButton.IconOnly
            onClicked: view.detailsRequested()
        }
    }
    ControlLabel { visible: view.detailed; Layout.fillWidth: true; font.pixelSize: Style.caption; opacity: 0.7; text: view.sink ? view.sink.description : i18n("No audio output"); elide: Text.ElideRight }
}
