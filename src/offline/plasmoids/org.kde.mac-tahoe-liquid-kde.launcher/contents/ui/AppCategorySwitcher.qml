import QtQuick
import QtQuick.Controls
import org.kde.kirigami as Kirigami

Item {
    id: scrollview

    property alias model: categorySwitcher.model
    property alias currentIndex: categorySwitcher.currentIndex
    implicitHeight: categorySwitcher.currentItem ? categorySwitcher.currentItem.implicitHeight : 0

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
        anchors.fill: parent

        readonly property var visibleSamples: {
            const result = [];
            for (const child of contentItem.children)
                if (child.pillSamples) result.push(...child.pillSamples);
            return result;
        }
        delegate: Item {
            id: del
            readonly property alias pillSamples: pill.samples
            required property var model
            required property var index
            implicitWidth: pill.implicitWidth
            implicitHeight: pill.implicitHeight
            height: categorySwitcher.height

            // ListView owns the delegate position; center its contents instead.
            CategoryPill {
                id: pill
                anchors.verticalCenter: parent.verticalCenter
                viewport: categorySwitcher
                selected: categorySwitcher.currentIndex == del.index
                text: del.model.name

                // Emit on click only: currentIndex also moves when the
                // category list rebuilds, and that must not switch views.
                onClicked: {
                    categorySwitcher.currentIndex = del.index
                    scrollview.categorySwitched(del.model.modelIndex)
                }
            }
        }

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
