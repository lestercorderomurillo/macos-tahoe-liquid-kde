import QtQuick
import QtQuick.Controls.Basic

ScrollBar {
    id: control
    z: 2
    implicitWidth: 12
    padding: 0

    contentItem: Rectangle {
        implicitWidth: 10
        implicitHeight: 100
        radius: width / 2
        color: control.pressed ?  main.textColor : main.dimmedTextColor
        // Hide the ScrollBar when it's not needed.
        opacity: control.policy === ScrollBar.AlwaysOn || (control.active && control.size < 1.0) ? 0.75 : 0

        // Animate the changes in opacity (default duration is 250 ms).
        Behavior on opacity {
            NumberAnimation {}
        }
    }


    background: Rectangle{
        color: control.active ? main.contrastBgColor : "transparent"
        opacity: control.policy === ScrollBar.AlwaysOn || (control.active && control.size < 1.0) ? 1 : 0

        // Animate the changes in opacity (default duration is 250 ms).
        Behavior on opacity {
            NumberAnimation {}
        }
        radius: width / 2
    }
}