// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import LauncherInteraction 1.0
Timer {
    interval: 350
    running: true
    repeat: true
    property int phase: 0
    property int waits: 0
    function verify(ok, message) { if (!ok) throw new Error(message); }
    onTriggered: {
        try {
            if (phase === 0) {
                root.visible = true;
                main.showClipboard(true);
            } else if (phase === 1) {
                if (!main.clipboard.available && ++waits < 20) return;
                verify(main.clipboard.available, "real daemon available");
                verify(main.clipboard.entries.length === 3, "history loaded");
                verify(!main.detachedSearch, "history shares its search surface");
                verify(!appList.visible && !searchList.visible, "applications hidden in history mode");
                main.searchText = "second";
            } else if (phase === 2) {
                verify(clipboardView.entries.length === 1, "query filters clipboard");
                main.clipboard.pin(clipboardView.entries[0].id, true);
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
                main.clipboard.clear();
            } else if (phase === 8) {
                verify(main.clipboard.entries.length === 1 && main.clipboard.entries[0].pinned, "clear retains pins");
                console.log("CLIPBOARD_LAUNCHER_OK");
                stop();
            }
            ++phase;
        } catch (error) {
            console.log("CLIPBOARD_LAUNCHER_FAILED", phase, error);
            stop();
        }
    }
}
