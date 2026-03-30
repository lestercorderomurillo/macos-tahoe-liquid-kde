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
        source: main.showAllApps ? Qt.resolvedUrl('icons/AppsIcon.svg') : "favorite-symbolic"
        isMask: main.showAllApps
        color: main.dimmedTextColor
        MouseArea {
            anchors.fill: parent
            onClicked: {
                main.showAllApps = !main.showAllApps;
                textField.forceActiveFocus(Qt.BacktabFocusReason)
            }
        }
    }

    TextField {
        id: textField
        Layout.fillHeight: true
        Layout.fillWidth: true
        font.pointSize: 18

        placeholderText: i18n("Applications")
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

    SessionButtons {
        id: sessionButtons
        visible: plasmoid.configuration.showSessionActionsButton
    }

    MenuButton {
        id: menuButton
    }
}