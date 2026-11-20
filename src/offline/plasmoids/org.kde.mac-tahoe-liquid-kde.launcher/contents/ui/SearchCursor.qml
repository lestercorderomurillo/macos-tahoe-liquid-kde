import QtQuick

Item {
    id: cursor
    required property TextInput field

    width: 2
    readonly property int flashTime: Qt.styleHints.cursorFlashTime
    readonly property bool blinking: visible && field.activeFocus
        && field.selectionStart === field.selectionEnd && flashTime > 0
    property bool illuminated: true

    Timer {
        id: blink
        interval: Math.max(1, cursor.flashTime / 2)
        repeat: true
        running: cursor.blinking
        onTriggered: cursor.illuminated = !cursor.illuminated
        onRunningChanged: cursor.illuminated = true
    }
    Connections {
        target: cursor.field
        function onCursorPositionChanged() {
            if (cursor.blinking) blink.restart();
            cursor.illuminated = true;
        }
    }
    Item {
        anchors.fill: parent
        visible: cursor.illuminated && cursor.field.activeFocus
            && cursor.field.selectionStart === cursor.field.selectionEnd
        Image {
            anchors.centerIn: parent
            width: 26
            height: parent.height + 18
            source: "icons/SearchCursorGlow.svg"
            fillMode: Image.Stretch
        }
        Rectangle {
            anchors.fill: parent
            color: "white"
            radius: width / 2
        }
    }
}
