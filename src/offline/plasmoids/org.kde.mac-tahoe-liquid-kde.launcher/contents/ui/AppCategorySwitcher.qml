import QtQuick
import QtQuick.Controls
import org.kde.kirigami as Kirigami

Item {
    id: scrollview

    property alias model: categorySwitcher.model
    property alias currentIndex: categorySwitcher.currentIndex
    implicitHeight: Math.ceil(categoryFont.height) + 12

    FontMetrics {
        id: categoryFont
        font.family: Kirigami.Theme.defaultFont.family
        font.pointSize: main.appTextSize * 1.28
    }

    signal categorySwitched(int index)

    ListView {
        id: categorySwitcher
        spacing: 8
        // Share spare space between the labels. Long translations scroll at their natural width.
        readonly property real pillPadding: {
            if (!model || !model.length) return 10;
            let labelsWidth = 0;
            for (const category of model)
                labelsWidth += Math.ceil(categoryFont.advanceWidth(category.name));
            return Math.max(10, (width - labelsWidth - spacing * (model.length - 1)) / (2 * model.length));
        }
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
            implicitWidth: Math.ceil(categoryFont.advanceWidth(model.name)) + 2 * categorySwitcher.pillPadding
            implicitHeight: pill.implicitHeight
            height: categorySwitcher.height

            // ListView owns the delegate position; center its contents instead.
            CategoryPill {
                id: pill
                width: del.width
                labelFont: categoryFont.font
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
