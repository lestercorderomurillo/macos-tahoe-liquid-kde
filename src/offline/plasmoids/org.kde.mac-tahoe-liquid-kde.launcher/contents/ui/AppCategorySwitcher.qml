import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui/NotificationContrast.js" as Contrast
import QtQuick
import QtQuick.Controls
import org.kde.kirigami as Kirigami

Item {
    id: scrollview

    property alias model: categorySwitcher.model
    property alias currentIndex: categorySwitcher.currentIndex
    implicitHeight: categorySwitcher.currentItem ? categorySwitcher.currentItem.implicitHeight : 0

    signal categorySwitched(int index)

    readonly property real themeLightness: Contrast.luminance(main.textColor)
    readonly property color alternate: themeLightness > 0.179 ? "black" : "white"
    property bool useAlternate: false
    readonly property color rowInk: useAlternate && root.glassSettings.dynamicTinting ? alternate : main.textColor
    readonly property bool preferAlternate: {
        let total = 0, votes = 0;
        for (const cell of categorySwitcher.contentItem.children) {
            if (!cell.categoryPill) continue;
            for (const sample of cell.categoryPill.samples) {
                const surface = Contrast.luminance(sample);
                const themeRatio = Contrast.ratio(themeLightness, surface);
                const otherRatio = Contrast.ratio(Contrast.luminance(alternate), surface);
                if (themeRatio < 4.5 && otherRatio >= Math.max(4.5, themeRatio * 1.25)) ++votes;
                ++total;
            }
        }
        return total > 0 && votes >= total * (useAlternate ? 0.55 : 0.8);
    }
    onPreferAlternateChanged: settle.restart()
    onThemeLightnessChanged: { useAlternate = false; settle.restart(); }
    Timer {
        id: settle
        interval: 250
        onTriggered: scrollview.useAlternate = scrollview.preferAlternate
    }

    ListView {
        id: categorySwitcher
        spacing: main.detachedSearch ? Kirigami.Units.smallSpacing * 2.5 : 7
        orientation: ListView.Horizontal
        interactive: contentWidth > width
        boundsBehavior: Flickable.StopAtBounds
        flickDeceleration: 1500
        clip: true
        highlightResizeDuration: 0
        highlightMoveDuration: 50
        anchors.fill: parent

        delegate: Item {
            id: del
            property alias categoryPill: pill
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
                rowInk: scrollview.rowInk
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
