import QtQuick
import org.kde.kirigami as Kirigami

Item {
    id: pill
    property alias text: label.text
    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight

    required property Item viewport
    readonly property color textInk: main.categoryForeground(pill, viewport, samples)
    property bool selected: false
    readonly property color baseFill: main.isDarkTheme
            ? Qt.rgba(1, 1, 1, selected ? 0.12 : 0.06)
            : Qt.rgba(1, 1, 1, main.goldenGateLight
                ? (selected ? 0.68 : 0.52) : (selected ? 0.62 : 0.46))
    readonly property var samples: main.categorySamples(label, viewport, main.layerOver(baseFill, Qt.rgba(feedback.color.r, feedback.color.g, feedback.color.b, feedback.visible ? feedback.opacity : 0)))
    readonly property bool hovered: pointer.containsMouse
    readonly property bool pressed: pointer.pressed
    signal clicked

    Text {
        id: label
        anchors.fill: parent
        topPadding: 4
        bottomPadding: topPadding
        leftPadding: 8
        rightPadding: leftPadding
        font.family: Kirigami.Theme.defaultFont.family
        font.pointSize: main.appTextSize

        color: pill.textInk
    }

    Rectangle {
        id: pillBg
        anchors.fill: parent
        z: -1
        color: pill.baseFill
        radius: main.tahoeStyle ? 9 : 8
        border.width: main.tahoeStyle ? 1 : 0
        border.color: Qt.rgba(1, 1, 1, pill.selected ? 0.18 : 0.08)

        Rectangle {
            id: feedback
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
