// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import LauncherInteraction 1.0
Timer {
    interval: 350
    running: true
    repeat: true
    property int phase: -1
    property int waits: 0
    property string pinnedId: ""
    function verify(ok, message) { if (!ok) throw new Error(message); }
    onTriggered: {
        try {
            if (phase === -1) {
                root.visible = true;
            } else if (phase === 0) {
                LauncherInteraction.click(main.searchBar.testMenuButton.testButton);
                for (let i = 0; i < 5; ++i) LauncherInteraction.key(Qt.Key_Down);
                LauncherInteraction.key(Qt.Key_Return);
                verify(main.clipboardMode, "options menu opens clipboard history");
            } else if (phase === 1) {
                if (!main.clipboard.available && ++waits < 20) return;
                verify(main.clipboard.available, "real daemon available");
                verify(main.clipboard.entries.length === 3, "history loaded");
                verify(!main.detachedSearch, "history shares its search surface");
                verify(!appList.visible && !searchList.visible, "applications hidden in history mode");
                main.searchText = "second";
            } else if (phase === 2) {
                verify(clipboardView.entries.length === 1, "query filters clipboard");
                pinnedId = clipboardView.entries[0].id;
                main.clipboard.pin(pinnedId, true);
            } else if (phase === 3) {
                verify(clipboardView.entries[0].pinned, "live pin notification");
                main.searchText = "";
            } else if (phase === 4) {
                verify(clipboardView.entries[0].pinned, "pins sort first");
                clipboardView.choose();
            } else if (phase === 5) {
                verify(!root.visible, "successful copy dismisses launcher");
                verify(main.clipboard.entries.length === 0, "hidden view drops cached history");
                root.visible = true;
                main.showClipboard(false);
            } else if (phase === 6) {
                verify(!main.clipboard.active && appList.visible, "return to applications");
                main.showClipboard(true);
            } else if (phase === 7) {
                const loaded = main.clipboard.active && main.clipboard.available
                    && main.clipboard.entries.length === 3;
                if (!loaded && ++waits < 20) return;
                verify(loaded, "history reloaded before clear");
                main.clipboard.clear();
            } else if (phase === 8) {
                // The D-Bus action and its subsequent list notification are asynchronous.
                // Assert the final state, not whether both replies arrived within one timer tick.
                const retained = main.clipboard.entries.length === 1
                    && main.clipboard.entries[0].id === pinnedId && main.clipboard.entries[0].pinned;
                verify(main.clipboard.error === "", "clear action failed: " + main.clipboard.error);
                if (!retained && ++waits < 20) return;
                verify(retained, "clear retains the exact pinned entry");
                console.log("CLIPBOARD_LAUNCHER_OK");
                stop();
            }
            waits = 0;
            ++phase;
        } catch (error) {
            console.log("CLIPBOARD_LAUNCHER_FAILED", phase, error);
            stop();
        }
    }
}
