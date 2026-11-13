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

        color: pill.selected ? main.textColor : main.dimmedTextColor
        layer.enabled: true
        layer.effect: GlassTextShadow {}
    }

    Rectangle {
        id: pillBg
        anchors.fill: parent
        z: -1
        color: main.isDarkTheme
            ? Qt.rgba(1, 1, 1, selected ? 0.12 : 0.06)
            : Qt.rgba(1, 1, 1, main.goldenGateLight
                ? (selected ? 0.68 : 0.52) : (selected ? 0.62 : 0.46))
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
