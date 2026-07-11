import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import org.kde.kirigami as Kirigami

RowLayout {

    property alias textField: textField
    property alias showMenuButton: menuButton.visible

    Kirigami.Icon {
        id: searchIcon
        Layout.rightMargin: 0
        source: Qt.resolvedUrl('icons/AppsIcon.svg')
        isMask: true
        color: main.dimmedTextColor
    }

    TextField {
        id: textField
        Layout.fillHeight: true
        Layout.fillWidth: true
        font.pointSize: 18

        placeholderText: i18n("Apps")
        placeholderTextColor: main.dimmedTextColor
        background: Rectangle{
            color: "transparent"
        }
        focus: true
        onTextChanged: {
            textField.forceActiveFocus(Qt.ShortcutFocusReason)
            runnerModel.query = text;   
        }

        Keys.onPressed: event => {
            if (event.key == Qt.Key_Escape) {
                event.accepted = true;
                if (searching) {
                    clear();
                } else {
                    root.toggle()
                }
            }

        }
    }

    MenuButton {
        id: menuButton
    }
}