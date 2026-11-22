// SPDX-License-Identifier: GPL-3.0-only
import QtQuick
import QtQuick.Layouts
import org.kde.mac.tahoe.launcher as NativeLauncher
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore

PlasmoidItem {
    id: root
    NativeLauncher.DockCell {
        id: dockCell
        applet: root
        active: Plasmoid.formFactor === PlasmaCore.Types.Horizontal
            || Plasmoid.formFactor === PlasmaCore.Types.Vertical
        vertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical
    }
    Plasmoid.constraintHints: Plasmoid.CanFillArea
    Layout.fillWidth: dockCell.active
    Layout.fillHeight: dockCell.active
    Layout.minimumWidth: Plasmoid.formFactor === PlasmaCore.Types.Horizontal ? Math.floor(dockCell.size) : 0
    Layout.preferredWidth: Plasmoid.formFactor === PlasmaCore.Types.Horizontal ? dockCell.size : -1
    Layout.maximumWidth: Plasmoid.formFactor === PlasmaCore.Types.Horizontal ? dockCell.preferredSize : Infinity
    Layout.minimumHeight: Plasmoid.formFactor === PlasmaCore.Types.Vertical ? Math.floor(dockCell.size) : 0
    Layout.preferredHeight: Plasmoid.formFactor === PlasmaCore.Types.Vertical ? dockCell.size : -1
    Layout.maximumHeight: Plasmoid.formFactor === PlasmaCore.Types.Vertical ? dockCell.preferredSize : Infinity

    Plasmoid.title: i18n("Downloads")
    Plasmoid.icon: "folder-download"
    Plasmoid.status: popup.visible ? PlasmaCore.Types.RequiresAttentionStatus : PlasmaCore.Types.PassiveStatus
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    toolTipMainText: i18n("Downloads")
    toolTipSubText: i18n("Open recent files or drag them into an application")
    preferredRepresentation: fullRepresentation
    Plasmoid.onActivated: popup.visible = !popup.visible

    RecentFiles { id: recent }

    function openFolder() {
        Qt.openUrlExternally(recent.folder);
        popup.visible = false;
    }
    Plasmoid.contextualActions: [PlasmaCore.Action {
        text: i18n("Open Downloads")
        icon.name: "folder-open"
        onTriggered: root.openFolder()
    }]

    fullRepresentation: NativeLauncher.DockIcon {
        location: Plasmoid.location
        inPanel: dockCell.active
        hovered: pointer.containsMouse
        source: Plasmoid.icon
        active: pointer.containsMouse || popup.visible
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: i18n("Downloads")
        Accessible.onPressAction: Plasmoid.activated()
        Keys.onSpacePressed: Plasmoid.activated()
        Keys.onReturnPressed: Plasmoid.activated()
        MouseArea {
            id: pointer
            anchors.fill: parent
            hoverEnabled: true
            onClicked: Plasmoid.activated()
        }
    }
    PlasmaCore.Dialog {
        id: popup
        visualParent: root.fullRepresentationItem
        location: Plasmoid.location
        type: PlasmaCore.Dialog.AppletPopup
        backgroundHints: PlasmaCore.Dialog.NoBackground
        hideOnWindowDeactivate: !recent.frozen
        mainItem: DownloadsFan {
            files: recent
            width: implicitWidth
            height: implicitHeight
            onDraggingChanged: recent.frozen = dragging
            onOpenFile: file => {
                Qt.openUrlExternally(file);
                popup.visible = false;
            }
            onOpenFolder: root.openFolder()
            onDismissed: popup.visible = false
        }
    }
}
