// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.volume as Audio
ColumnLayout {
    id: view
    Audio.SinkModel { id: outputs }
    property var sink: outputs.defaultSink
    QQC.Label { text: i18n("Sound"); font.bold: true }
    RowLayout {
        QQC.ToolButton {
            icon.name: view.sink && view.sink.muted ? "audio-volume-muted" : "audio-volume-high"
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
    QQC.Label { Layout.fillWidth: true; text: view.sink ? view.sink.description : i18n("No audio output"); elide: Text.ElideRight }
}
