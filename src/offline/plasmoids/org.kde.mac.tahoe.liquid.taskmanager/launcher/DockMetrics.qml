// SPDX-License-Identifier: GPL-3.0-only
pragma Singleton
import QtQuick
import org.kde.kirigami as Kirigami

QtObject {
    id: root
    property var cells: []

    function add(cell) {
        cells = cells.concat([cell]);
        schedule();
    }
    function remove(cell) {
        cells = cells.filter(c => c !== cell);
        schedule();
    }
    function schedule() { Qt.callLater(root.recalculate); }
    function recalculate() {
        const groups = new Map();
        for (const cell of cells) {
            if (!cell.active || !cell.applet.visible || !cell.panelWindow) continue;
            if (!groups.has(cell.panelWindow)) groups.set(cell.panelWindow, []);
            groups.get(cell.panelWindow).push(cell);
        }
        for (const group of groups.values()) {
            const manager = group.find(c => c.taskManager && c.count > 0);
            if (!manager) {
                for (const cell of group) cell.size = cell.vertical ? cell.applet.width : cell.applet.height;
                continue;
            }
            const vertical = manager.vertical;
            const members = group.filter(c => c.vertical === vertical);
            let available = 0;
            let count = 0;
            for (const cell of members) {
                available += vertical ? cell.applet.height : cell.applet.width;
                count += cell.count;
                if (cell.taskManager) available -= Math.max(0, cell.count - 1) * cell.spacing;
            }
            if (available <= 0 || count <= 0) continue;
            const thickness = vertical ? manager.applet.width : manager.applet.height;
            const size = Math.max(Math.min(thickness, Kirigami.Units.iconSizes.small),
                                  Math.min(thickness, available / count));
            for (const cell of members) {
                // Queuing the calculation avoids a Layout/geometry binding loop;
                // preserve subpixel sizing while ignoring rounding noise.
                if (Math.abs(cell.size - size) > 0.1) cell.size = size;
            }
        }
    }
}
