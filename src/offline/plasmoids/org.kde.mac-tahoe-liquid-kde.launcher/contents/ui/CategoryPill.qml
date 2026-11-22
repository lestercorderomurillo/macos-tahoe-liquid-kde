import "../../../org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui/NotificationContrast.js" as Contrast
import QtQuick
import org.kde.kirigami as Kirigami

Item {
    id: pill
    property alias text: label.text
    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight

    required property Item viewport
    required property color rowInk
    property bool selected: false
    readonly property color baseFill: main.isDarkTheme
            ? Qt.rgba(1, 1, 1, selected ? 0.12 : 0.06)
            : Qt.rgba(1, 1, 1, main.goldenGateLight
                ? (selected ? 0.68 : 0.52) : (selected ? 0.62 : 0.46))
    readonly property var samples: main.categorySamples(label, viewport, baseFill)
    readonly property color correctedFill: {
        const ink = Contrast.luminance(rowInk);
        const shade = ink > 0.179 ? 0 : 1;
        // Use only as much neutral fill as the poorest sampled region needs.
        for (let step = 0; step <= 12; ++step) {
            const overlay = Qt.rgba(shade, shade, shade, step / 32);
            if (step === 12 || samples.every(sample =>
                Contrast.ratio(ink, Contrast.luminance(Qt.tint(sample, overlay))) >= 4.5))
                return main.layerOver(baseFill, overlay);
        }
        return baseFill;
    }

    readonly property bool hovered: pointer.containsMouse
    readonly property bool pressed: pointer.pressed
    signal clicked

    Text {
        id: label
        anchors.fill: parent
        topPadding: main.detachedSearch ? Kirigami.Units.smallSpacing * 1.25 : 4
        bottomPadding: topPadding
        leftPadding: main.detachedSearch ? Kirigami.Units.smallSpacing * 3 : 8
        rightPadding: leftPadding
        font.family: Kirigami.Theme.defaultFont.family
        font.pointSize: main.appTextSize

        color: pill.rowInk
    }

    Rectangle {
        id: pillBg
        anchors.fill: parent
        z: -1
        color: pill.correctedFill
        radius: main.detachedSearch ? height * 0.45 : (main.tahoeStyle ? 9 : 8)
        border.width: main.tahoeStyle ? 1 : 0
        border.color: Qt.rgba(1, 1, 1, pill.selected ? 0.18 : 0.08)

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            visible: main.tahoeStyle
            color: main.isDarkTheme ? "white" : main.textColor
            opacity: pill.pressed ? 0.14 : (pill.hovered ? 0.08 : 0)
            Behavior on opacity { NumberAnimation { duration: 100 } }
        }
    }

    MouseArea {
        id: pointer
        hoverEnabled: main.tahoeStyle
        anchors.fill: pill
        onClicked: pill.clicked();
    }
}
