// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.plasma5support as Support
Support.DataSource {
    engine: "executable"
    function run(action) {
        // Plasma sessions can omit the installer’s per-user binary directory.
        const themeSwitch = "sh -c 'PATH=\"$PATH:$HOME/.local/bin\" exec mac-tahoe-theme-switch \"$1\"' sh ";
        const commands = {
            // The engine closes its pipes once setsid returns; a detached
            // kcmshell6 writing its startup warnings would die of SIGPIPE.
            acrylic: "setsid -f kcmshell6 --icon draw-brush-symbolic --caption 'Acrylic Glass' "
                     + (Qt.platform.pluginName === "xcb" ? "kwin-x11" : "kwin")
                     + "/effects/configs/kwin_liquidglass_config >/dev/null 2>&1",
            sharing: "kdeconnect-app",
            overview: "qdbus6 org.kde.kglobalaccel /component/kwin org.kde.kglobalaccel.Component.invokeShortcut Overview",
            display: "systemsettings kcm_kscreen",
            auto: themeSwitch + "auto",
            dark: themeSwitch + "dark",
            light: themeSwitch + "light",
            screenshot: "spectacle -r -d 300"
        };
        if (commands[action]) connectSource(commands[action]);
    }
    onNewData: (sourceName, data) => disconnectSource(sourceName)
}
