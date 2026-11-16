// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "ControlStyle.js" as Style
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.mpris as Media
ColumnLayout {
    id: view
    Media.Mpris2Model { id: players }
    property var player: players.currentPlayer
    Item {
        Layout.preferredWidth: 38; Layout.preferredHeight: 38; Layout.minimumHeight: 38
        Rectangle { anchors.fill: parent; radius: 9; color: "#20808080" }
        Kirigami.Icon { anchors.centerIn: parent; width: 24; height: 24; source: Style.symbol("audio-x-generic"); visible: !cover.status || cover.status !== Image.Ready }
        Image { id: cover; anchors.fill: parent; source: view.player ? view.player.artUrl : ""; fillMode: Image.PreserveAspectCrop }
    }
    ControlLabel { Layout.fillWidth: true; Layout.minimumWidth: 0; text: view.player ? view.player.track || view.player.identity : i18n("Nothing playing"); elide: Text.ElideRight }
    ControlLabel { Layout.fillWidth: true; visible: !!view.player; font.pixelSize: Style.caption; opacity: 0.7; text: view.player ? view.player.artist : ""; elide: Text.ElideRight }
    RowLayout {
        Layout.fillWidth: true
        spacing: 0
        QQC.ToolButton { font.family: "SF Pro Text"; font.pixelSize: 13; Layout.fillWidth: true; padding: 2; icon.width: 20; icon.height: 20; icon.source: Style.symbol("media-skip-backward"); text: i18n("Previous track"); Accessible.name: text; display: QQC.AbstractButton.IconOnly; enabled: !!view.player && view.player.canGoPrevious; onClicked: view.player.Previous() }
        QQC.ToolButton { font.family: "SF Pro Text"; font.pixelSize: 13; Layout.fillWidth: true; padding: 2; icon.width: 20; icon.height: 20; icon.source: Style.symbol(view.player && view.player.playbackStatus === Media.PlaybackStatus.Playing ? "media-playback-pause" : "media-playback-start"); text: i18n("Play or pause"); Accessible.name: text; display: QQC.AbstractButton.IconOnly; enabled: !!view.player && (view.player.canPlay || view.player.canPause); onClicked: view.player.PlayPause() }
        QQC.ToolButton { font.family: "SF Pro Text"; font.pixelSize: 13; Layout.fillWidth: true; padding: 2; icon.width: 20; icon.height: 20; icon.source: Style.symbol("media-skip-forward"); text: i18n("Next track"); Accessible.name: text; display: QQC.AbstractButton.IconOnly; enabled: !!view.player && view.player.canGoNext; onClicked: view.player.Next() }
    }
}
