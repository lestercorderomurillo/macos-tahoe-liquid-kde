// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Window
import org.kde.mac.tahoe.launcher 1.0

Item {
    id: scene
    width: 800
    height: 600
    Item { id: first; x: 100; y: 250; width: 400; height: 200 }
    Item { id: second; x: 200; y: 300; width: 360; height: 180 }
    LauncherSearchPopup {
        id: popup
        visualParent: first
        width: 200
        height: 80
        margin: 12
        popupDirection: Qt.TopEdge
    }
    Timer {
        interval: 200
        running: true
        repeat: true
        property int phase: 0
        onTriggered: {
            if (phase++ === 0) { popup.visible = true; return; }
            const anchor = popup.visualParent;
            const expected = anchor.mapToGlobal(anchor.width / 2, 0).x;
            const actual = popup.x + popup.width / 2;
            if (Math.abs(expected - actual) > 1) {
                console.error("ANCHOR_FAILED", phase, expected, actual);
                stop(); Qt.exit(1); return;
            }
            switch (phase) {
            case 2: first.width += 80; break;
            case 3: first.x += 35; break;
            case 4: popup.width += 40; break;
            case 5: popup.visualParent = second; break;
            case 6:
                first.width += 120;
                second.width += 60;
                break;
            case 7: scene.Window.window.x += 30; break;
            case 8:
                popup.visible = false;
                second.x -= 40;
                second.width -= 80;
                popup.visible = true;
                break;
            default:
                console.log("ANCHOR_OK"); stop(); Qt.exit(0);
            }
        }
    }
}
