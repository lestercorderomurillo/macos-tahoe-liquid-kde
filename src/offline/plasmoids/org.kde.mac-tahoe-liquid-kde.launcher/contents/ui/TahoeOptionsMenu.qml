import QtQuick
import QtQuick.Controls as Controls
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.extras as PlasmaExtras

PlasmaCore.Dialog {
    id: menu
    property Item anchorItem
    property list<QtObject> actions
    readonly property var content: actions
    readonly property int status: visible ? PlasmaExtras.Menu.Open : PlasmaExtras.Menu.Closed
    visualParent: anchorItem
    type: PlasmaCore.Dialog.PopupMenu
    flags: Qt.Popup | Qt.FramelessWindowHint
    location: PlasmaCore.Types.Floating
    onYChanged: if (visible) Qt.callLater(alignBelow)
    onVisibleChanged: if (visible) Qt.callLater(alignBelow)
    function alignBelow() {
        if (!visible) return;
        const position = anchorItem.mapToGlobal(anchorItem.width, 0);
        x = Math.round(position.x - width);
        y = Math.round(position.y);
    }
    hideOnWindowDeactivate: true

    function openRelative() {
        const position = anchorItem.mapToGlobal(anchorItem.width, 0);
        selectedIndex = -1;
        visible = true;
        x = Math.round(position.x - width);
        y = Math.round(position.y);
        requestActivate();
        menuBody.forceActiveFocus();
    }
    function close() {
        const wasVisible = visible;
        visible = false;
        if (wasVisible && root.visible) main.focusSearch();
    }
    property int selectedIndex: -1
    function moveSelection(direction) {
        let index = selectedIndex;
        for (let count = 0; count < actions.length; ++count) {
            index = (index + direction + actions.length) % actions.length;
            const action = actions[index];
            if (!action.section && !action.separator && action.enabled) {
                selectedIndex = index;
                return;
            }
        }
    }
    function activate(index) {
        if (index < 0 || index >= actions.length) return;
        const action = actions[index];
        if (action.section || action.separator || !action.enabled) return;
        visible = false;
        action.clicked();
        if (root.visible) main.focusSearch();
    }

    mainItem: FocusScope {
        id: menuBody
        width: 154 - dialogSvg.margins.left - dialogSvg.margins.right
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
                    required property var modelData
                    required property int index
                    width: rows.width
                    height: modelData.separator ? 10 : modelData.section ? 23 : 24
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
                            color: main.isDarkTheme ? "#40ffffff" : "#30000000"
                        }
                    }
                    contentItem: Item {
                        Text {
                            visible: row.modelData.checkable && row.modelData.checked
                            width: 12
                            anchors.verticalCenter: parent.verticalCenter
                            horizontalAlignment: Text.AlignHCenter
                            text: "✓"
                            font.family: main.textFont
                            font.pointSize: main.textSize
                            color: label.color
                        }
                        Text {
                            id: label
                            visible: !row.modelData.separator
                            anchors.left: parent.left
                            anchors.leftMargin: 16
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.verticalCenterOffset: row.modelData.section ? 2.5 : 0
                            text: row.modelData.text
                            font.family: main.textFont
                            font.pointSize: main.textSize * (row.modelData.section ? 0.85 : 1.05)
                            font.weight: row.modelData.section ? Font.DemiBold : Font.Normal
                            color: row.enabled && menu.selectedIndex === row.index ? "white"
                                : row.modelData.section ? Qt.rgba(main.textColor.r, main.textColor.g, main.textColor.b, 0.55)
                                : main.isDarkTheme ? "#f2f2f2" : main.textColor
                        }
                    }
                    padding: 0
                }
            }
        }
    }
}
