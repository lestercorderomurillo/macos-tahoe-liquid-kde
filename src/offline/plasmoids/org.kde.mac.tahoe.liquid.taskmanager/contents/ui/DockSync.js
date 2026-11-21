// SPDX-License-Identifier: GPL-3.0-or-later
// Shared by every Dock in the shell (one QML engine): pinning, unpinning or
// reordering on one screen is mirrored to the Docks on the other screens.
.pragma library

var docks = [];

function register(dock) {
    if (docks.indexOf(dock) < 0) docks.push(dock);
}

function unregister(dock) {
    const i = docks.indexOf(dock);
    if (i >= 0) docks.splice(i, 1);
}

// Last pin list shared by the Docks; a change from any Dock that differs
// from it is mirrored to the others.
var current = null;

function publish(source, launchers) {
    const key = String(launchers);
    if (current === null) { current = key; return; } // first Dock sets the baseline
    if (key === current) return;
    current = key;
    for (const dock of docks.slice()) {
        if (dock !== source) dock.adoptLaunchers(launchers);
    }
}
