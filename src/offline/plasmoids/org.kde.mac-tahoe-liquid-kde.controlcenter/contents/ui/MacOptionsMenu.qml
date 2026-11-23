// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import org.kde.mac.tahoe.launcher as NativeGlass
import QtQuick.Window
import QtQuick.Controls as Controls
import QtQuick.Shapes
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami
import org.kde.ksvg as KSvg

PlasmaCore.Dialog {
    id: menu
    title: "mttkde-options"
    property NativeGlass.PopupBackdrop backdrop: NativeGlass.PopupBackdrop { window: menu }
    property NativeGlass.GlassSettings contrastSettings: NativeGlass.GlassSettings {}
    objectName: "macOptionsMenu"
    property var availableGeometry: () => Qt.rect(Screen.virtualX, Screen.virtualY, Screen.width, Screen.height)
    property string textFont: Kirigami.Theme.defaultFont.family
    property real textSize: Kirigami.Theme.defaultFont.pointSize
    property color textColor: Kirigami.Theme.textColor
    property bool isDarkTheme: textColor.r * 0.2126 + textColor.g * 0.7152 + textColor.b * 0.0722 > 0.5
    property int preferredWidth: 154
    property bool fitContents: false
    signal restoreFocusRequested()
    property Item anchorItem
    property list<QtObject> actions
    readonly property var content: actions
    readonly property int status: visible ? PlasmaExtras.Menu.Open : PlasmaExtras.Menu.Closed
    // Position explicitly before mapping; Dialog's anchor placement would
    // otherwise overwrite it for the first visible frame.
    visualParent: null
    // Keep the client glass contour; a menu role adds a compositor outline.
    type: PlasmaCore.Dialog.AppletPopup
    // A Qt.Popup is repositioned by Wayland independently of Dialog.x/y,
    // leaving hover coordinates out of sync with our Plasma shell surface.
    flags: Qt.Tool | Qt.FramelessWindowHint
    transientParent: anchorItem ? anchorItem.Window.window : null
    location: PlasmaCore.Types.Floating
    onXChanged: if (visible) alignBelow()
    onYChanged: if (visible) alignBelow()
    onWidthChanged: if (visible) alignBelow()
    onHeightChanged: if (visible) alignBelow()
    onVisibleChanged: if (visible) alignBelow()
    function alignBelow() {
        if (!anchorItem) return;
        const below = anchorItem.mapToGlobal(anchorItem.width, anchorItem.height);
        const above = anchorItem.mapToGlobal(0, 0);
        const area = menu.availableGeometry();
        x = Math.round(Math.max(area.x, Math.min(below.x - width, area.x + area.width - width)));
        y = Math.round(below.y + height <= area.y + area.height ? below.y : Math.max(area.y, above.y - height));
    }
    hideOnWindowDeactivate: true

    function openRelative() {
        selectedIndex = -1;
        alignBelow();
        visible = true;
        alignBelow();
        requestActivate();
        menuBody.forceActiveFocus();
    }
    function close() {
        const wasVisible = visible;
        visible = false;
        if (wasVisible) restoreFocusRequested();
    }
    property int selectedIndex: -1
    function moveSelection(direction) {
        let index = selectedIndex;
        for (let count = 0; count < actions.length; ++count) {
            index = (index + direction + actions.length) % actions.length;
            const action = actions[index];
            if (action.visible && !action.section && !action.separator && action.enabled) {
                selectedIndex = index;
                return;
            }
        }
    }
    function activate(index) {
        if (index < 0 || index >= actions.length) return;
        const action = actions[index];
        if (!action.visible || action.section || action.separator || !action.enabled) return;
        visible = false;
        action.clicked();
        restoreFocusRequested();
    }

    mainItem: FocusScope {
        id: menuBody
        Binding on width {
            delayed: true
            value: Math.max(menu.preferredWidth, menu.fitContents ? menuBody.contentWidth() : 0)
                - dialogSvg.margins.left - dialogSvg.margins.right
        }
        function contentWidth() {
            let width = 0;
            for (const action of menu.actions) {
                if (action.visible) width = Math.max(width, labelMetrics.advanceWidth(action.text));
            }
            return Math.min(menu.availableGeometry().width, Math.ceil(width) + 32 + dialogSvg.margins.left + dialogSvg.margins.right);
        }
        KSvg.FrameSvgItem { id: dialogSvg; visible: false; imagePath: "dialogs/background" }
        FontMetrics { id: labelMetrics; font.family: menu.textFont; font.pointSize: menu.textSize * 1.05 }
        height: rows.height
        focus: true
        Keys.onPressed: event => {
            switch (event.key) {
            case Qt.Key_Down: menu.moveSelection(1); break;
            case Qt.Key_Up: menu.moveSelection(-1); break;
            case Qt.Key_Tab: menu.moveSelection(event.modifiers & Qt.ShiftModifier ? -1 : 1); break;
            case Qt.Key_Return:
            case Qt.Key_Enter: menu.activate(menu.selectedIndex); break;
            case Qt.Key_Escape: menu.close(); break;
            default: return;
            }
            event.accepted = true;
        }
        Column {
            id: rows
            width: parent.width
            Repeater {
                model: menu.actions
                delegate: Controls.ItemDelegate {
                    id: row
                    objectName: "launcherOption"
                    required property var modelData
                    required property int index
                    width: rows.width
                    visible: modelData.visible
                    height: !visible ? 0 : modelData.separator ? 10 : modelData.section ? 23 : 24
                    enabled: !modelData.section && !modelData.separator && modelData.enabled
                    focusPolicy: Qt.NoFocus
                    hoverEnabled: enabled
                    Accessible.name: modelData.text
                    Accessible.role: Accessible.MenuItem
                    Accessible.checkable: modelData.checkable
                    Accessible.checked: modelData.checked
                    onHoveredChanged: {
                        if (hovered) menu.selectedIndex = index;
                        else if (menu.selectedIndex === index) menu.selectedIndex = -1;
                    }
                    onClicked: menu.activate(index)
                    background: Rectangle {
                        radius: 8
                        color: row.enabled && menu.selectedIndex === row.index ? "#0a84ff" : "transparent"
                        Rectangle {
                            visible: row.modelData.separator
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.leftMargin: 4
                            anchors.rightMargin: 4
                            height: 0.5
                            color: menu.isDarkTheme ? "#40ffffff" : "#30000000"
                        }
                    }
                    contentItem: Item {
                        Shape {
                            preferredRendererType: Shape.CurveRenderer
                            visible: row.modelData.checkable && row.modelData.checked
                            width: 9
                            height: 9
                            anchors.left: parent.left
                            anchors.leftMargin: 2.5
                            anchors.verticalCenter: parent.verticalCenter

                            ShapePath {
                                fillColor: "transparent"
                                strokeColor: label.color
                                strokeWidth: 1.4
                                capStyle: ShapePath.RoundCap
                                joinStyle: ShapePath.RoundJoin
                                startX: 1.2
                                startY: 4.8
                                PathLine { x: 3.4; y: 7.5 }
                                PathLine { x: 8; y: 1.2 }
                            }
                        }
                        FontMetrics {
                            id: rowMetrics
                            font: label.font
                        }
                        Text {
                            id: label
                            visible: !row.modelData.separator
                            anchors.left: parent.left
                            anchors.leftMargin: 16
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            readonly property rect inkBounds: rowMetrics.tightBoundingRect(text)
                            // Allow one pixel for the rasterized font's optical alignment.
                            anchors.verticalCenterOffset: row.modelData.section ? 2.5
                                : height / 2 - baselineOffset - inkBounds.y - inkBounds.height / 2 + 1
                            text: row.modelData.text
                            elide: Text.ElideRight
                            font.family: menu.textFont
                            font.pointSize: menu.textSize * (row.modelData.section ? 0.85 : 1.05)
                            font.weight: row.modelData.section ? Font.DemiBold : Font.Normal
                            readonly property color baseInk: row.enabled && menu.selectedIndex === row.index ? "white"
                                : row.modelData.section ? Qt.rgba(menu.textColor.r, menu.textColor.g, menu.textColor.b, 0.55)
                                : menu.textColor
                            color: menu.contrastSettings.dynamicTinting
                                ? NativeGlass.AdaptiveContrast.foreground(menu.backdrop, label, baseInk, row.background.color)
                                : baseInk
                        }
                    }
                    padding: 0
                    // The desktop style sets bottomPadding independently of padding.
                    topPadding: 0
                    bottomPadding: 0
                }
            }
        }
    }
}
