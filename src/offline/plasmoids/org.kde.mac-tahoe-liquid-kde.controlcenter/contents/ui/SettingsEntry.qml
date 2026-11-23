// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support

PlasmaCore.Action {
    id: entry

    required property int widgetId
    readonly property bool available: launcher.available

    text: i18nd("plasma_applet_org.kde.mac-tahoe-liquid-kde.controlcenter", "Configure in Settings…")
    icon.name: "configure"
    visible: available
    onTriggered: launcher.connectSource(launcher.program + "--section=dock_bar --widget=" + widgetId)

    readonly property P5Support.DataSource launcher: P5Support.DataSource {
        engine: "executable"
        property bool available: false
        readonly property string program: "sh -c 'exec \"$HOME/.local/bin/mac-tahoe-settings\" \"$@\"' settings "
        readonly property string check: program + "--available"
        connectedSources: [check]
        onNewData: (source, data) => {
            if (source === check)
                available = Number(data["exit code"]) === 0;
            disconnectSource(source);
        }
    }
}
