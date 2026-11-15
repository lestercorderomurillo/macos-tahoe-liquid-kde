// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import org.kde.plasma.extras as PlasmaExtras

FocusScope {
    id: view
    readonly property bool menuOpen: actions.visible
    property var actionItem: null
    property bool clearArmed: false
    readonly property var entries: {
        const query = main.searchText.trim().toLocaleLowerCase();
        return main.clipboard.entries.filter(item => {
            const text = item.kind === "image" ? i18n("Image") : item.text;
            return !query || text.toLocaleLowerCase().includes(query);
        }).sort((a, b) => Number(b.pinned) - Number(a.pinned) || b.ts - a.ts);
    }
    onEntriesChanged: list.currentIndex = Math.min(Math.max(0, list.currentIndex), entries.length - 1)
    onVisibleChanged: if (!visible) { actions.close(); clearArmed = false; }
    function more(anchor, item) {
        actionItem = item;
        clearArmed = false;
        actions.anchorItem = anchor;
        actions.openRelative();
    }
    function choose() {
        if (list.currentIndex >= 0 && list.currentIndex < entries.length)
            main.clipboard.copy(entries[list.currentIndex].id);
    }
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Down) list.incrementCurrentIndex();
        else if (event.key === Qt.Key_Up) list.decrementCurrentIndex();
        else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) choose();
        else if (event.key === Qt.Key_Delete && list.currentIndex >= 0) {
            const item = entries[list.currentIndex];
            if (!item.pinned) main.clipboard.remove(item.id);
        } else if (event.key === Qt.Key_P && (event.modifiers & Qt.ControlModifier) && list.currentIndex >= 0) {
            const item = entries[list.currentIndex];
            main.clipboard.pin(item.id, !item.pinned);
        } else if (event.key === Qt.Key_Menu && list.currentItem) view.more(list.currentItem, entries[list.currentIndex]);
        else return;
        event.accepted = true;
    }
    ListView {
        id: list
        objectName: "clipboardHistory"
        anchors.fill: parent
        clip: true
        model: view.entries
        spacing: 0
        boundsBehavior: Flickable.StopAtBounds
        keyNavigationWraps: false
        Controls.ScrollBar.vertical: Controls.ScrollBar {}
        delegate: Controls.ItemDelegate {
            id: row
            required property var modelData
            required property int index
            width: list.width
            height: Math.round(main.textSize * 5.2)
            padding: 8
            hoverEnabled: true
            onHoveredChanged: if (hovered) list.currentIndex = index
            onClicked: main.clipboard.copy(modelData.id)
            Accessible.name: (modelData.kind === "image" ? i18n("Image") : modelData.text)
            background: Rectangle {
                radius: 10
                color: list.currentIndex === row.index ? main.contrastBgColor : "transparent"
            }
            contentItem: RowLayout {
                spacing: 14
                Item {
                    Layout.preferredWidth: 36
                    Layout.preferredHeight: 40
                    Kirigami.Icon {
                        anchors.fill: parent
                        source: row.modelData.kind === "image" ? "image-x-generic" : "text-plain"
                        visible: thumbnail.status !== Image.Ready
                    }
                    Image {
                        id: thumbnail
                        anchors.fill: parent
                        source: row.modelData.kind === "image" ? row.modelData.imageUrl : ""
                        sourceSize: Qt.size(72, 80)
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        Layout.fillWidth: true
                        text: row.modelData.kind === "image" ? i18n("Image") + " · " + row.modelData.w + " × " + row.modelData.h : row.modelData.text.replace(/\s+/g, " ")
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        maximumLineCount: 1
                        font.family: main.textFont
                        font.pointSize: main.textSize * 1.2
                        color: main.textColor
                    }
                    Text {
                        Layout.fillWidth: true
                        text: (row.modelData.pinned ? i18n("Pinned") + " · " : "")
                            + (row.modelData.kind === "image" ? i18n("Image") : i18n("Text"))
                            + " · " + i18n("Copied %1", Qt.formatDateTime(new Date(row.modelData.ts), "h:mm ap"))
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        font.family: main.textFont
                        font.pointSize: main.textSize
                        color: main.dimmedTextColor
                        opacity: 0.75
                    }
                }
                Controls.ToolButton {
                    Layout.preferredWidth: 28
                    Layout.preferredHeight: 28
                    padding: 7
                    contentItem: Kirigami.Icon {
                        source: Qt.resolvedUrl("icons/ClipboardIcon.svg")
                        isMask: true
                        color: main.textColor
                    }
                    Accessible.name: i18n("Copy")
                    Controls.ToolTip.visible: hovered
                    Controls.ToolTip.text: i18n("Copy")
                    onClicked: main.clipboard.copy(row.modelData.id)
                    background: Rectangle { radius: width / 2; color: main.contrastBgColor }
                }

            }
        }
    }
    Text {
        anchors.centerIn: parent
        width: parent.width - 32
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        textFormat: Text.PlainText
        color: main.textColor
        font.family: main.textFont
        font.pointSize: main.textSize
        visible: view.entries.length === 0 || main.clipboard.error !== ""
        text: main.clipboard.error ? i18n("Clipboard action failed. Try again.") : (!main.clipboard.available
            ? i18n("Clipboard history is unavailable. Enable Clipboard history in the installer.")
            : main.searchText ? i18n("No results") : i18n("Nothing copied yet"))
    }
    TahoeOptionsMenu {
        id: actions
        actions: [
            PlasmaExtras.MenuItem {
                text: view.actionItem ? (view.actionItem.pinned ? i18n("Unpin") : i18n("Pin")) : i18n("Applications")
                onClicked: {
                    if (view.actionItem) main.clipboard.pin(view.actionItem.id, !view.actionItem.pinned);
                    else main.showClipboard(false);
                }
            },
            PlasmaExtras.MenuItem {
                text: view.actionItem ? i18n("Delete") : view.clearArmed ? i18n("Confirm clear history") : i18n("Clear history")
                enabled: main.clipboard.available && (!view.actionItem || !view.actionItem.pinned)
                onClicked: {
                    if (view.actionItem) main.clipboard.remove(view.actionItem.id);
                    else if (view.clearArmed) { main.clipboard.clear(); view.clearArmed = false; }
                    else { view.clearArmed = true; Qt.callLater(() => actions.openRelative()); }
                }
            }
        ]
    }
}
