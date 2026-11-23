// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Effects
import "ControlStyle.js" as Style
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.mpris as Media
ColumnLayout {
    id: view
    Media.Mpris2Model { id: players }
    property var player: players.currentPlayer
    readonly property bool hasTrack: !!player && !!player.track
    spacing: 6
    Item {
        Layout.preferredWidth: 39; Layout.preferredHeight: 39; Layout.minimumHeight: 39
        // macOS Tahoe: a light translucent artwork placeholder.
        Rectangle { anchors.fill: parent; radius: 9; color: Qt.rgba(1, 1, 1, 0.14) }
        Kirigami.Icon { anchors.centerIn: parent; width: 24; height: 24; source: Style.symbol("audio-x-generic"); isMask: true; color: Style.foreground(this, Window.window, Kirigami.Theme.textColor); visible: view.hasTrack && cover.status !== Image.Ready }
        Image {
            id: cover
            anchors.fill: parent
            source: view.hasTrack ? view.player.artUrl : ""
            fillMode: Image.PreserveAspectCrop
            // Same 9 px corners as the empty artwork placeholder.
            layer.enabled: status === Image.Ready
            layer.effect: MultiEffect { maskEnabled: true; maskSource: artMask; maskThresholdMin: 0.5; maskSpreadAtMin: 1.0 }
        }
        Rectangle { id: artMask; anchors.fill: parent; radius: 9; visible: false; layer.enabled: true; layer.smooth: true }
    }
    ControlLabel { Layout.fillWidth: true; Layout.minimumWidth: 0; objectName: "trackTitle"; wrapMode: Text.Wrap; maximumLineCount: 2; font.pixelSize: Style.tileTitle; font.weight: Font.DemiBold; text: view.hasTrack ? view.player.track : i18n("Nothing playing"); elide: Text.ElideRight }
    ControlLabel { Layout.fillWidth: true; visible: view.hasTrack && text.length > 0; font.pixelSize: Style.caption; opacity: 0.7; text: view.player ? view.player.artist : ""; elide: Text.ElideRight }
    RowLayout {
        Layout.fillWidth: true
        spacing: 0
        ControlIconButton { font.family: "SF Pro Text"; font.pixelSize: 13; Layout.fillWidth: true; padding: 2; icon.width: 20; icon.height: 20; icon.source: Style.symbol("media-skip-backward"); text: i18n("Previous track"); Accessible.name: text; display: QQC.AbstractButton.IconOnly; enabled: !!view.player && view.player.canGoPrevious; onClicked: view.player.Previous() }
        ControlIconButton { font.family: "SF Pro Text"; font.pixelSize: 13; Layout.fillWidth: true; padding: 2; icon.width: 20; icon.height: 20; icon.source: Style.symbol(view.player && view.player.playbackStatus === Media.PlaybackStatus.Playing ? "media-playback-pause" : "media-playback-start"); text: i18n("Play or pause"); Accessible.name: text; display: QQC.AbstractButton.IconOnly; enabled: !!view.player && (view.player.canPlay || view.player.canPause); onClicked: view.player.PlayPause() }
        ControlIconButton { font.family: "SF Pro Text"; font.pixelSize: 13; Layout.fillWidth: true; padding: 2; icon.width: 20; icon.height: 20; icon.source: Style.symbol("media-skip-forward"); text: i18n("Next track"); Accessible.name: text; display: QQC.AbstractButton.IconOnly; enabled: !!view.player && view.player.canGoNext; onClicked: view.player.Next() }
    }
}
