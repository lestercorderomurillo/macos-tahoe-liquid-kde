import QtQuick
import org.kde.kirigami as Kirigami

Item {
    id: pill
    property alias text: label.text
    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight

    property bool selected: false
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

        color: main.labelColor(label, width / 2, pillBg.color)
        font.weight: pill.selected ? Font.DemiBold : Font.Medium
    }

    Rectangle {
        id: pillBg
        anchors.fill: parent
        z: -1
        color: main.isDarkTheme
            ? Qt.rgba(0, 0, 0, selected ? 0.66 : 0.76)
            : Qt.rgba(1, 1, 1, main.goldenGateLight
                ? (selected ? 0.80 : 0.66) : (selected ? 0.78 : 0.64))
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
