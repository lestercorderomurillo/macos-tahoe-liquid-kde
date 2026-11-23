// SPDX-License-Identifier: GPL-2.0-or-later
import QtQuick
import org.kde.plasma.plasma5support as P5Support

P5Support.DataSource {
    id: route

    property bool available: false
    readonly property string program: "sh -c 'exec \"$HOME/.local/bin/mac-tahoe-settings\" \"$@\"' settings "
    readonly property string check: program + "--available"

    engine: "executable"
    connectedSources: [check]
    onNewData: (source, data) => {
        if (source === check)
            available = Number(data["exit code"]) === 0;
        disconnectSource(source);
    }

    function open(widgetId: int) {
        route.connectSource(program + "--section=dock_bar --widget=" + widgetId);
    }
}
