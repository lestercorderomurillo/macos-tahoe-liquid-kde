// SPDX-License-Identifier: GPL-3.0-only
import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

FocusScope {
    id: fan
    required property var files
    property bool dragging: false
    signal openFile(url file)
    signal openFolder()
    signal dismissed()
    implicitWidth: Kirigami.Units.gridUnit * 22
    implicitHeight: Kirigami.Units.gridUnit * (5 + Math.max(1, files.entries.length) * 3.5)
    Keys.onEscapePressed: dismissed()

    Controls.Label {
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        text: i18n("Downloads")
        font.bold: true
        padding: Kirigami.Units.smallSpacing
        background: Rectangle {
            radius: Kirigami.Units.cornerRadius
            color: Qt.alpha(Kirigami.Theme.backgroundColor, 0.9)
        }
    }
    Controls.Label {
        anchors.centerIn: parent
        width: parent.width - Kirigami.Units.largeSpacing * 2
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: i18n("No completed downloads yet")
        visible: fan.files.entries.length === 0
        padding: Kirigami.Units.largeSpacing
        background: Rectangle {
            radius: Kirigami.Units.cornerRadius
            color: Qt.alpha(Kirigami.Theme.backgroundColor, 0.9)
        }
    }
    Item {
        id: cards
        anchors.top: parent.top
        anchors.topMargin: Kirigami.Units.gridUnit * 2
        anchors.bottom: folderButton.top
        anchors.bottomMargin: Kirigami.Units.largeSpacing
        anchors.left: parent.left
        anchors.right: parent.right
        Repeater {
            id: stack
            model: fan.files.entries
            delegate: FileCard {
                id: entry
                required property int index
                required property var modelData
                fileName: modelData.name
                fileUrl: modelData.url
                width: Math.min(implicitWidth, cards.width * 0.8)
                height: implicitHeight
                x: (cards.width - width) / 2 + Math.pow(index / 6, 2) * Kirigami.Units.gridUnit * 2
                y: cards.height - height - index * Math.min(height * 1.12, (cards.height - height) / Math.max(1, stack.count - 1))
                rotation: -index * 2
                z: stack.count - index
                onFileOpened: file => fan.openFile(file)
                onDragBegan: fan.dragging = true
                onDragEnded: { fan.dragging = false; fan.dismissed(); }
                KeyNavigation.up: index + 1 < stack.count ? stack.itemAt(index + 1) : folderButton
                KeyNavigation.down: index > 0 ? stack.itemAt(index - 1) : folderButton
            }
        }
    }
    Controls.Button {
        id: folderButton
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Kirigami.Units.gridUnit
        anchors.horizontalCenter: parent.horizontalCenter
        text: i18n("Open Downloads")
        implicitWidth: folderLabel.implicitWidth + Kirigami.Units.largeSpacing * 2
        implicitHeight: Kirigami.Units.gridUnit * 2
        contentItem: Controls.Label {
            id: folderLabel
            text: folderButton.text
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            color: folderButton.hovered || folderButton.visualFocus
                ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
        }
        background: Rectangle {
            radius: Kirigami.Units.cornerRadius
            color: folderButton.hovered || folderButton.visualFocus
                ? Kirigami.Theme.highlightColor : Qt.alpha(Kirigami.Theme.backgroundColor, 0.95)
        }
        onClicked: fan.openFolder()
        KeyNavigation.up: stack.count ? stack.itemAt(0) : null
        KeyNavigation.down: stack.count ? stack.itemAt(stack.count - 1) : null
    }
    onVisibleChanged: if (visible) folderButton.forceActiveFocus()
}
