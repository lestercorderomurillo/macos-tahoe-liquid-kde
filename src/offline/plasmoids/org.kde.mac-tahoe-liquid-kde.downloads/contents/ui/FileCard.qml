// SPDX-License-Identifier: GPL-3.0-only
import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

Controls.AbstractButton {
    id: card
    required property string fileName
    required property url fileUrl
    signal fileOpened(url file)
    signal dragBegan()
    signal dragEnded()
    property bool dragging: false

    text: fileName
    implicitWidth: Kirigami.Units.gridUnit * 17
    implicitHeight: Kirigami.Units.gridUnit * 3
    focusPolicy: Qt.StrongFocus
    Accessible.name: fileName
    Accessible.description: i18n("Open this file, or drag it into an application")
    onClicked: if (!dragging) fileOpened(fileUrl)

    background: Rectangle {
        radius: Kirigami.Units.cornerRadius
        color: card.hovered || card.visualFocus
            ? Kirigami.Theme.highlightColor : Kirigami.Theme.backgroundColor
        opacity: card.hovered || card.visualFocus ? 0.95 : 0.85
        border.width: 1
        border.color: Qt.alpha(Kirigami.Theme.textColor, 0.12)
    }
    contentItem: Item {
        Kirigami.Icon {
            id: fileIcon
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: Kirigami.Units.iconSizes.medium
            height: width
            source: "text-x-generic"
            opacity: thumbnail.status === Image.Ready ? 0 : 1
        }
        Image {
            id: thumbnail
            anchors.fill: fileIcon
            source: /\.(png|jpe?g|webp|gif)$/i.test(card.fileName) ? card.fileUrl : ""
            sourceSize: Qt.size(128, 128)
            asynchronous: true
            fillMode: Image.PreserveAspectFit
            visible: status === Image.Ready
        }
        Controls.Label {
            anchors.left: fileIcon.right
            anchors.leftMargin: Kirigami.Units.smallSpacing
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: card.fileName
            textFormat: Text.PlainText
            elide: Text.ElideMiddle
            color: card.hovered || card.visualFocus
                ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
        }
    }
    Controls.ToolTip.visible: hovered && !dragging
    Controls.ToolTip.text: fileName
    Controls.ToolTip.textFormat: Text.PlainText
    Controls.ToolTip.delay: Kirigami.Units.toolTipDelay

    DragHandler {
        id: gesture
        target: null
        acceptedButtons: Qt.LeftButton
        onActiveChanged: {
            if (active) {
                card.dragging = true;
                card.dragBegan();
                card.grabToImage(result => {
                    if (!gesture.active) {
                        card.dragging = false;
                        card.dragEnded();
                        return;
                    }
                    card.Drag.imageSource = result.url;
                    card.Drag.active = true;
                });
            }
        }
    }
    Drag.dragType: Drag.Automatic
    Drag.mimeData: ({"text/uri-list": fileUrl.toString() + "\r\n"})
    Drag.supportedActions: Qt.CopyAction | Qt.MoveAction | Qt.LinkAction
    Drag.proposedAction: Qt.CopyAction
    Drag.hotSpot: Qt.point(width / 2, height / 2)
    Drag.onDragFinished: {
        Drag.active = false;
        dragging = false;
        dragEnded();
    }
}
