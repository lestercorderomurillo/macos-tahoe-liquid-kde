// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "ControlStyle.js" as Style
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.volume as Audio
ColumnLayout {
    id: view
    Audio.SinkModel { id: outputs }
    property var sink: outputs.defaultSink
    ControlLabel { text: i18n("Sound"); font.weight: Font.DemiBold }
    RowLayout {
        QQC.ToolButton { font.family: "SF Pro Text"; font.pixelSize: 13;
            icon.source: Style.symbol(view.sink && view.sink.muted ? "audio-volume-muted" : "audio-volume-high")
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
            onMoved: view.sink.volume = Math.round(value)
        }
    }
    ControlLabel { Layout.fillWidth: true; font.pixelSize: Style.caption; opacity: 0.7; text: view.sink ? view.sink.description : i18n("No audio output"); elide: Text.ElideRight }
}
