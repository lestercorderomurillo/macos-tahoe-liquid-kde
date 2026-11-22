import QtQuick
import org.kde.kirigami as Kirigami

Item {
    id: cursor
    required property TextInput field

    width: 2
    readonly property int flashTime: Qt.styleHints.cursorFlashTime
    readonly property bool focusedCaret: field.activeFocus && field.selectionStart === field.selectionEnd
    readonly property bool blinking: visible && focusedCaret && flashTime > 0
    readonly property int fadeDuration: Math.min(Kirigami.Units.shortDuration, flashTime / 6)
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
        visible: cursor.focusedCaret
        opacity: !cursor.blinking || cursor.illuminated ? 1 : 0
        Behavior on opacity {
            enabled: cursor.blinking && cursor.fadeDuration > 0
            NumberAnimation {
                duration: cursor.fadeDuration
                easing.type: Easing.InOutSine
            }
        }
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
