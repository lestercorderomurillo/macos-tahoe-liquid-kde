// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.plasma5support as Support
Support.DataSource {
    engine: "executable"
    function run(action) {
        const commands = {
            sharing: "kdeconnect-app",
            overview: "qdbus6 org.kde.kglobalaccel /component/kwin org.kde.kglobalaccel.Component.invokeShortcut Overview",
            display: "systemsettings kcm_kscreen",
            dark: "mac-tahoe-theme-switch dark",
            light: "mac-tahoe-theme-switch light",
            screenshot: "spectacle -r -d 300"
        };
        if (commands[action]) connectSource(commands[action]);
    }
    onNewData: (sourceName, data) => disconnectSource(sourceName)
}
