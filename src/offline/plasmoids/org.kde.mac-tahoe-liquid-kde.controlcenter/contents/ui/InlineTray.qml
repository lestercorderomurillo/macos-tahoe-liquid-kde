// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "ControlStyle.js" as Style
import QtQuick.Layouts
import QtQuick.Controls as QQC
import QtQml.Models
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents
import org.kde.mac.tahoe.launcher as Native

Item {
    id: strip
    required property Item tray
    required property Item stockArrow
    readonly property GridView grid: tray.hiddenLayout
    property bool revealed: false

    parent: stockArrow.parent
    Layout.row: 0
    Layout.column: 1
    Layout.fillHeight: true
    implicitWidth: controls.implicitWidth
    implicitHeight: controls.implicitHeight
    visible: icons.count > 0
    onVisibleChanged: if (!visible) revealed = false

    // The tray shortcut and the Back action can request the old overview.
    // Allow native applet details to open, and route overview requests here.
    function routeOverview() {
        const state = tray.systemTrayState;
        if (state.expanded && !state.activeApplet) {
            state.expanded = false;
            revealed = true;
        }
    }
    Connections {
        target: strip.tray.systemTrayState
        function onExpandedChanged() { Qt.callLater(strip.routeOverview); }
        function onActiveAppletChanged() { Qt.callLater(strip.routeOverview); }
    }

    Binding { target: strip.stockArrow; property: "visible"; value: false }
    // Reuse Plasma's delegate and status model. Keep a single delegate per
    // applet so its native click, scroll and context actions stay attached.
    ListModel { id: emptyModel }
    Binding { target: strip.grid; property: "model"; value: emptyModel }
    Binding { target: strip.grid; property: "cellWidth"; value: strip.tray.visibleLayout.cellWidth }
    Binding { target: strip.grid; property: "cellHeight"; value: Math.max(1, strip.height) }
    function glyphs(item: Item): list<Item> {
        if (item instanceof Kirigami.Icon) return [item];
        const matches = [];
        for (const child of item.children) matches.push(...glyphs(child));
        return matches;
    }
    Instantiator {
        model: (icons.contentItem.children ?? []).filter(child => child.item?.iconContainer).map(child => child.item)
        delegate: QtObject {
            id: slot
            required property Item modelData
            readonly property Item icon: modelData.iconContainer
            readonly property Item layout: icon.parent
            readonly property Item label: layout?.children.find(child => child instanceof PlasmaComponents.Label) ?? null
            property Instantiator iconColors: Instantiator {
                model: strip.glyphs(slot.icon)
                delegate: Binding {
                    required property Item modelData
                    target: modelData
                    property: "color"
                    value: ink.foreground
                }
            }
            property Binding labelVisibility: Binding { target: slot.label; property: "visible"; when: !!slot.label; value: false }
            property Binding padding: Binding { target: slot.layout; property: "anchors.margins"; value: 0 }
            property Binding iconWidth: Binding { target: slot.icon; property: "implicitWidth"; value: strip.tray.itemSize }
            property Binding iconHeight: Binding { target: slot.icon; property: "implicitHeight"; value: strip.tray.itemSize }
            property Binding tooltip: Binding { target: slot.modelData; property: "mainText"; value: slot.modelData.text }
        }
    }

    // Panel Colorizer attaches a background to the strip. Only the icons
    // and their toggle should occupy cells in the tray layout.
    RowLayout {
        id: controls
        anchors.fill: parent
        spacing: 0

        GridView {
            id: icons
            Kirigami.Theme.textColor: ink.foreground
            visible: strip.revealed
            Layout.fillHeight: true
            Layout.preferredWidth: Math.min(count * cellWidth, strip.Screen.width / 3)
            flow: GridView.TopToBottom
            cellWidth: strip.grid.cellWidth
            cellHeight: strip.grid.cellHeight
            boundsBehavior: Flickable.StopAtBounds
            clip: true
            model: strip.tray.hiddenModel
            delegate: strip.grid.delegate
        }

        QQC.ToolButton {
            id: toggle
            Layout.preferredWidth: Math.max(Style.panelButtonWidth, strip.stockArrow.implicitWidth)
            Layout.fillHeight: true
            checkable: true
            checked: strip.revealed
            onClicked: strip.revealed = !strip.revealed
            Accessible.name: strip.revealed ? i18n("Hide hidden icons") : i18n("Show hidden icons")
            background: PanelCapsule { visible: toggle.hovered || toggle.visualFocus }
            contentItem: Kirigami.Icon {
                source: strip.revealed ? "arrow-right-symbolic" : "arrow-left-symbolic"
                isMask: true
                color: ink.foreground
                implicitWidth: 16
                implicitHeight: 16
            }
            padding: 2
            leftPadding: padding + Math.max(0, width - strip.stockArrow.implicitWidth) / 2
            rightPadding: leftPadding
            Native.WallpaperInk { id: ink; item: toggle; base: toggle.Kirigami.Theme.textColor }
        }
    }
}
