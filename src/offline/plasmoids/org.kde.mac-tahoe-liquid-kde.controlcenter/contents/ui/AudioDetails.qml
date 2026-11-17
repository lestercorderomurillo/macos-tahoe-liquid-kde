// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick.Layouts
Page {
    AudioView { Layout.fillWidth: true; detailed: true }
    SettingsLink { text: i18n("Audio outputs"); module: "kcm_pulseaudio" }
}
