// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Window
import org.kde.plasma.core as PlasmaCore
import org.kde.mac.tahoe.launcher

Item {
    PlasmaCore.Dialog {
        id: panel
        location: PlasmaCore.Types.Floating
        type: PlasmaCore.Dialog.AppletPopup
        flags: Qt.WindowStaysOnTopHint
        hideOnWindowDeactivate: false
        mainItem: Item { width: 600; height: 400 }
    }
    LauncherSearchPopup {
        id: capsule
        visualParent: panel.contentItem
        transientParent: panel
        popupDirection: Qt.TopEdge
        margin: 12
        width: 300
        height: 80
    }
    Timer {
        interval: 250
        running: true
        repeat: true
        property int phase: 0
        property int target: 0
        property int retries: 0
        function openOn(index) {
            target = index;
            const output = Qt.application.screens[index];
            panel.x = output.virtualX + (output.width - panel.width) / 2;
            panel.y = output.virtualY + (output.height - panel.height) / 2 + 50;
            panel.visible = true;
            // Map in the same turn, before the parent's new output-enter event.
            capsule.visible = true;
        }
        function verify() {
            const output = Qt.application.screens[target];
            if (Math.abs(capsule.x + capsule.width / 2 - panel.x - panel.width / 2) > 1
                || Math.abs(capsule.y + capsule.height + capsule.margin - panel.y) > 1
                || capsule.x < output.virtualX || capsule.x + capsule.width > output.virtualX + output.width
                || capsule.y < output.virtualY || capsule.y + capsule.height > output.virtualY + output.height) {
                throw new Error("screen " + target + ": panel=" + panel.x + "," + panel.y
                    + " size=" + panel.width + "x" + panel.height
                    + " anchor=" + panel.contentItem.width + "x" + panel.contentItem.height
                    + " capsule=" + capsule.x + "," + capsule.y + " size=" + capsule.width + "x" + capsule.height);
            }
        }
        onTriggered: {
            try {
                if (Qt.application.screens.length !== 2) throw new Error("two outputs required");
                switch (phase++) {
                case 0: openOn(0); break;
                case 1:
                    verify(); capsule.visible = false; panel.visible = false; break;
                case 2: openOn(1); break;
                case 3:
                    verify(); panel.mainItem.width = 720; break;
                case 4:
                    verify(); capsule.visible = false; panel.visible = false; break;
                case 5: openOn(0); break;
                case 6:
                    verify(); openOn(1); break;
                case 7:
                    verify(); panel.x += 25; break;
                case 8:
                    verify(); capsule.width = 360; break;
                default:
                    verify(); console.warn("LAUNCHER_SCREENS_OK"); stop(); Qt.exit(0);
                }
                retries = 0;
            } catch (error) {
                // Native output/configure events may lag on software-rendered CI.
                if (retries++ < 10) { --phase; return; }
                console.error("LAUNCHER_SCREENS_FAILED", phase, error);
                stop(); Qt.exit(1);
            }
        }
    }
}
