// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQml.Models
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents
import "ControlStyle.js" as Style

Item {
    id: menu
    required property GridView grid
    required property bool overview
    required property var rows

    // Plasma owns the rows, their actions, the header buttons and the detail pages.
    readonly property Item page: {
        for (let item = grid; item; item = item.parent) {
            if (item.hiddenLayout === grid) return item;
        }
        return null;
    }
    readonly property bool listPage: !!page && overview
    readonly property int rowHeight: 32
    readonly property int listHeight: Math.min(grid?.count ?? 0, 12) * rowHeight + 44

    Binding { target: menu.page; property: "Layout.minimumWidth"; when: menu.listPage; value: 284 }
    Binding { target: menu.page; property: "Layout.minimumHeight"; when: menu.listPage; value: menu.listHeight }
    Binding { target: menu.page; property: "Layout.preferredWidth"; when: menu.listPage; value: 284 }
    Binding { target: menu.page; property: "Layout.preferredHeight"; when: menu.listPage; value: menu.listHeight }
    Binding { target: menu.page; property: "Layout.maximumWidth"; when: menu.listPage; value: 284 }
    Binding { target: menu.page; property: "Layout.maximumHeight"; when: menu.listPage; value: menu.listHeight }
    readonly property Item heading: {
        const column = page?.children.find(item => item instanceof ColumnLayout);
        const header = column?.children.find(item => item instanceof RowLayout);
        return header?.children.find(item => item instanceof Kirigami.Heading) ?? null;
    }
    Binding { target: menu.heading; property: "font.family"; when: menu.listPage && !!menu.heading; value: Style.family }
    Binding { target: menu.heading; property: "font.pixelSize"; when: menu.listPage && !!menu.heading; value: 14 }
    Binding { target: menu.heading; property: "font.weight"; when: menu.listPage && !!menu.heading; value: Font.DemiBold }
    Binding { target: menu.grid; property: "cellWidth"; when: !!menu.grid; value: menu.grid?.width ?? 0 }
    Binding { target: menu.grid; property: "cellHeight"; when: !!menu.grid; value: menu.rowHeight }
    Binding { target: menu.grid; property: "highlight"; when: !!menu.grid; value: selection }

    Component {
        id: selection
        Rectangle {
            radius: 8
            color: Kirigami.Theme.textColor.hslLightness > .5 ? Qt.rgba(1, 1, 1, .12) : Qt.rgba(0, 0, 0, .08)
        }
    }

    Instantiator {
        model: menu.rows
        delegate: QtObject {
            id: row
            required property Item modelData
            readonly property Item icon: modelData.iconContainer
            readonly property Item layout: icon.parent
            readonly property Item label: layout?.children.find(item => item instanceof PlasmaComponents.Label) ?? null
            property Binding noTooltip: Binding { target: row.modelData; property: "active"; value: false }
            property Binding iconWidth: Binding { target: row.icon; property: "implicitWidth"; value: 24 }
            property Binding iconHeight: Binding { target: row.icon; property: "implicitHeight"; value: 24 }
            property Binding inset: Binding { target: row.layout; property: "anchors.leftMargin"; value: 8 }
            property Binding spacing: Binding { target: row.layout; property: "spacing"; value: 9 }
            property Binding typeface: Binding { target: row.label; property: "font.family"; when: !!row.label; value: Style.family }
            property Binding textSize: Binding { target: row.label; property: "font.pixelSize"; when: !!row.label; value: Style.body }
            property Binding singleLine: Binding { target: row.label; property: "maximumLineCount"; when: !!row.label; value: 1 }
        }
    }
}
