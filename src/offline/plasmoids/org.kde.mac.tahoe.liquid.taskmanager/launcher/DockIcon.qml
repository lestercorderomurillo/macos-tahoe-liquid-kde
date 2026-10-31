// SPDX-License-Identifier: GPL-2.0-or-later
import QtQuick
import org.kde.plasma.core as PlasmaCore
import org.kde.ksvg as KSvg
import org.kde.kirigami as Kirigami

// Match the task frame's asymmetric indicator margins (issue #115).
Item {
    id: root
    property alias source: icon.source
    property alias active: icon.active
    property bool inPanel: true
    property bool normalizeTrashArtwork: false
    // Bundled trash bodies occupy 53/64 vertically; app tiles occupy 56/64.
    // Correct their artwork padding without changing panel cells or task margins.
    // At 24px and below the theme uses separate small glyphs, not this artwork.
    readonly property bool normalizedTrash: normalizeTrashArtwork && inPanel
        && Math.min(iconBox.width, iconBox.height) > 24
        && (String(source) === "user-trash" || String(source) === "user-trash-full")
    readonly property real artworkScale: normalizedTrash ? 56 / 53 : 1
    property int location: PlasmaCore.Types.BottomEdge
    readonly property alias iconItem: icon
    implicitWidth: height
    implicitHeight: Kirigami.Units.iconSizes.large

    KSvg.FrameSvgItem {
        id: taskFrame
        visible: false
        imagePath: "widgets/tasks"
        prefix: {
            switch (root.location) {
            case PlasmaCore.Types.LeftEdge: return ["west-normal", "normal"];
            case PlasmaCore.Types.TopEdge: return ["north-normal", "normal"];
            case PlasmaCore.Types.RightEdge: return ["east-normal", "normal"];
            default: return ["south-normal", "normal"];
            }
        }
    }

    function adjustedMargin(size: real, margin: real, total: real): real {
        if (size > 0 && size - total < Kirigami.Units.iconSizes.small) {
            return Math.ceil((margin * (Kirigami.Units.iconSizes.small / size)) / 2);
        }
        return margin;
    }

    Item {
        id: iconBox
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        readonly property real leftInset: root.inPanel ? root.adjustedMargin(root.width,
            taskFrame.margins.left, taskFrame.margins.left + taskFrame.margins.right) : 0
        readonly property real rightInset: root.inPanel ? root.adjustedMargin(root.width,
            taskFrame.margins.right, taskFrame.margins.left + taskFrame.margins.right) : 0
        anchors.topMargin: root.inPanel ? root.adjustedMargin(root.height,
            taskFrame.margins.top, taskFrame.margins.top + taskFrame.margins.bottom) : 0
        readonly property real bottomInset: root.inPanel ? root.adjustedMargin(root.height,
            taskFrame.margins.bottom, taskFrame.margins.top + taskFrame.margins.bottom) : 0

        width: Math.max(0, Math.min(root.width, root.height) - leftInset - rightInset)
        height: Math.max(0, root.height - anchors.topMargin - bottomInset)

        Kirigami.Icon {
            id: icon
            // Let Kirigami fit the artwork inside the same rectangular box
            // as Task.qml, including device-pixel rounding at fractional scales.
            x: (parent.width - width) / 2
            // The trash body is centred at y=32.5 in its 64px canvas.
            y: (parent.height - height) / 2 - (root.normalizedTrash
                ? Math.min(parent.width, parent.height) * root.artworkScale / 128 : 0)
            width: parent.width * root.artworkScale
            height: parent.height * root.artworkScale
            smooth: true
        }
    }
}
