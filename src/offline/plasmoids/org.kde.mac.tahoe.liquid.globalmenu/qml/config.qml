/*
    SPDX-License-Identifier: GPL-2.0-or-later
*/
import org.kde.plasma.configuration
import plasma.applet.org.kde.mac.tahoe.liquid.globalmenu

ConfigModel {
    id: model

    readonly property SystemMenuSettingsLink settingsLink: SystemMenuSettingsLink {}

    ConfigCategory {
        name: i18n("Appearance")
        icon: "preferences-desktop-color"
        source: "configGeneral.qml"
    }
    ConfigCategory {
        name: i18n("System Menu")
        icon: "start-here-kde-symbolic"
        source: "configSystemMenu.qml"
        visible: !model.settingsLink.available
    }
}
