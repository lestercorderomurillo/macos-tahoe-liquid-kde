// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick.Layouts
Page {
    DisplayView { Layout.fillWidth: true; detailed: true }
    SettingsLink { text: i18n("Display Settings…"); module: "kcm_kscreen" }
}
