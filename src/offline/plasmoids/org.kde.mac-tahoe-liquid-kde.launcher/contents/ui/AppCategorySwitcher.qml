import QtQuick
import QtQuick.Controls

Item {
    id: scrollview

    property alias model: categorySwitcher.model

    signal categorySwitched(int index)

    ListView {
        id: categorySwitcher
        spacing: 7
        orientation: ListView.Horizontal
        interactive: contentWidth > width
        boundsBehavior: Flickable.StopAtBounds
        flickDeceleration: 1500
        clip: true
        highlightResizeDuration: 0
        highlightMoveDuration: 50
        property var contentHeight: 0

        anchors.topMargin: (parent.height - contentHeight) / 2
        anchors.fill: parent

        delegate: CategoryPill {
            id: del
            required property var model
            required property var index
            selected: categorySwitcher.currentIndex == index
            text: model.name

            onClicked: categorySwitcher.currentIndex = index

            Component.onCompleted: {
                categorySwitcher.contentHeight = del.height
            }
        }

        onCurrentIndexChanged: categorySwitched(categorySwitcher.currentItem.model.modelIndex)

        WheelHandler {
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: (event) => {
                if (event.angleDelta.x !== 0) {
                    categorySwitcher.flick(event.angleDelta.x * 15, 0);
                } else if (event.angleDelta.y !== 0) {
                    categorySwitcher.flick(event.angleDelta.y * 15, 0);
                }
            }
        }
    }
}
