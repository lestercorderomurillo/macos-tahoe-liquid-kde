import QtQuick 
import org.kde.kirigami as Kirigami

Text {
    id: pill

    property bool selected: false
    signal clicked

    topPadding: 4
    bottomPadding: topPadding
    leftPadding: 8
    rightPadding: 8
    font.pointSize: 10

    color: selected ? "#000000" : main.textColor
    opacity: selected ? 0.8 : 0.4

   Rectangle {
        id: pillBg
        anchors.fill: parent
        anchors.centerIn: parent
        z: -1
        color: selected ? Qt.rgba(255, 255, 255, 0.5) : main.isDarkTheme ? Qt.rgba(255, 255, 255, 0.2) : Qt.rgba(255, 255, 255, 0.5)
        radius: 8
    }

    MouseArea {
        anchors.fill: pill
        onClicked: pill.clicked();
    }
}
