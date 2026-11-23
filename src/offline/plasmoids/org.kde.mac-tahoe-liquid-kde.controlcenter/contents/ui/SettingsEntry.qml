// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support

PlasmaCore.Action {
    id: entry

    required property int widgetId
    property string section: "dock_bar"
    readonly property bool available: launcher.available
    signal launchFailed()

    text: i18nd("plasma_applet_org.kde.mac-tahoe-liquid-kde.controlcenter", "Configure in Settings…")
    icon.name: "configure"
    visible: available
    onTriggered: open()

    function open() {
        const instance = widgetId > 0 ? " --widget=" + widgetId : "";
        launcher.connectSource(launcher.program + "--section=" + section + instance);
    }

    readonly property P5Support.DataSource launcher: P5Support.DataSource {
        engine: "executable"
        property bool available: false
        readonly property string program: "sh -c 'exec \"$HOME/.local/bin/mac-tahoe-settings\" \"$@\"' settings "
        readonly property string check: program + "--available"
        connectedSources: [check]
        onNewData: (source, data) => {
            if (data["exit code"] === undefined) return;
            const succeeded = Number(data["exit code"]) === 0;
            disconnectSource(source);
            if (source === check)
                available = succeeded;
            else if (!succeeded)
                entry.launchFailed();
        }
    }
}
