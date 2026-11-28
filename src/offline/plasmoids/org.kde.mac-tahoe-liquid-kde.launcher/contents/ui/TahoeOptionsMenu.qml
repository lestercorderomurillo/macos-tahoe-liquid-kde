// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui" as Controls

Controls.MacOptionsMenu {
    id: launcherMenu
    notificationGlass: true
    materialComponent: "popups"
    property MouseArea outsidePress: MouseArea {
        id: dismissalArea
        parent: launcherMenu.visible ? root.contentItem : null
        anchors.fill: parent
        z: 1000
        acceptedButtons: Qt.AllButtons
        onPressed: mouse => {
            const anchor = launcherMenu.anchorItem;
            const onAnchor = anchor && anchor.contains(anchor.mapFromItem(dismissalArea, mouse.x, mouse.y));
            launcherMenu.visible = false;
            root.requestActivate();
            // Let the same press reach the textbox, category or app underneath.
            mouse.accepted = onAnchor;
        }
    }
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
