// SPDX-License-Identifier: GPL-2.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import org.kde.kitemmodels as KItemModels
import org.kde.plasma.private.kicker as Kicker
import org.kde.mac.tahoe.launcher as NativeLauncher
import QtQuick.Window

PlasmoidItem {
    id: root
    readonly property bool vertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical
    readonly property int gap: Math.round((vertical ? width : height) * 0.3)
    readonly property var manager: NativeLauncher.DockMetrics.cells.find(cell =>
        cell.taskManager && cell.panelWindow === root.Window.window)?.applet
    readonly property var excluded: manager?.visibleAppIds || []
    // Plasma insets this separator. Size its icons from the adjacent task manager.
    readonly property real iconThickness: vertical ? (manager?.width || width) : (manager?.height || height)
    readonly property int cellSize: NativeLauncher.DockMetrics.preferredCellSize(iconThickness)
    readonly property int length: gap + (recentApps.length ? gap + recentApps.length * cellSize : 0)
    property var recentApps: []
    Layout.minimumWidth: vertical ? 0 : length
    Layout.maximumWidth: vertical ? Infinity : length
    Layout.minimumHeight: vertical ? length : 0
    Layout.maximumHeight: vertical ? length : Infinity
    Kicker.RecentUsageModel {
        id: history
        shownItems: Kicker.RecentUsageModel.OnlyApps
        ordering: Kicker.RecentUsageModel.Recent
    }
    function updateRecentApps() {
        const result = [];
        const role = history.KItemModels.KRoleNames.role("favoriteId");
        for (let row = 0; row < history.count && result.length < 3; ++row) {
            const index = history.index(row, 0);
            const id = String(history.data(index, role) || "").split(/[/:]/).pop();
            if (!id || excluded.includes(id)) continue;
            result.push({row, name: history.data(index, Qt.DisplayRole),
                         icon: history.data(index, Qt.DecorationRole)});
        }
        recentApps = result;
    }
    onExcludedChanged: Qt.callLater(updateRecentApps)
    Connections {
        target: history
        function onModelReset() { Qt.callLater(root.updateRecentApps); }
        function onRowsInserted() { Qt.callLater(root.updateRecentApps); }
        function onRowsRemoved() { Qt.callLater(root.updateRecentApps); }
        function onRowsMoved() { Qt.callLater(root.updateRecentApps); }
        function onDataChanged() { Qt.callLater(root.updateRecentApps); }
    }
    Component.onCompleted: Qt.callLater(updateRecentApps)
    component Divider: Item {
        width: root.vertical ? root.width : root.gap
        height: root.vertical ? root.gap : root.height
        Rectangle {
            anchors.centerIn: parent
            width: root.vertical ? Math.round(parent.width * 0.62) : 1
            height: root.vertical ? 1 : Math.round(parent.height * 0.62)
            // A midtone hairline stays visible over both the light glass
            // and the dark parts of the edition wallpapers.
            color: Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.textColor, Kirigami.Theme.backgroundColor, 0.35)
            opacity: 0.65
        }
    }
    preferredRepresentation: fullRepresentation
    fullRepresentation: Grid {
        columns: root.vertical ? 1 : root.recentApps.length + 2
        Divider { visible: root.recentApps.length > 0 }
        Repeater {
            model: root.recentApps
            delegate: PlasmaCore.ToolTipArea {
                id: recent
                required property var modelData
                mainText: modelData.name
                width: root.vertical ? root.width : root.cellSize
                height: root.vertical ? root.cellSize : root.height
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: mainText
                function activate() { history.trigger(modelData.row, "", null); }
                Accessible.onPressAction: activate()
                Keys.onReturnPressed: activate()
                Keys.onSpacePressed: activate()
                NativeLauncher.DockIcon {
                    anchors.centerIn: parent
                    width: root.vertical ? root.iconThickness : recent.width
                    height: root.vertical ? recent.height : root.iconThickness
                    location: Plasmoid.location
                    source: recent.modelData.icon
                    hovered: hover.hovered
                    HoverHandler { id: hover }
                    TapHandler { onTapped: recent.activate() }
                }
            }
        }
        Divider {}
    }
}
