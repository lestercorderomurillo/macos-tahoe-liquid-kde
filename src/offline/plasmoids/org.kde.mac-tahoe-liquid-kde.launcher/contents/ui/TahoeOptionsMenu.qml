// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Controls

Controls.MacOptionsMenu {
    id: launcherMenu
    property Connections launcherVisibility: Connections {
        target: root
        function onVisibleChanged() {
            if (!root.visible) launcherMenu.close();
        }
    }
    objectName: "launcherOptionsMenu"
    availableGeometry: () => kicker.screenGeometry
    textFont: main.textFont
    textSize: main.textSize
    textColor: main.textColor
    isDarkTheme: main.isDarkTheme
    onRestoreFocusRequested: if (root.visible) main.focusSearch()
}
