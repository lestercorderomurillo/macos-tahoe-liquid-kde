import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM
import org.kde.iconthemes as KIconThemes
import org.kde.plasma.plasmoid

KCM.SimpleKCM {
    id: configGeneral

    property alias cfg_menuIcon: iconButton.currentIcon

    Kirigami.FormLayout {
        Kirigami.ActionTextField {
            id: iconField
            Kirigami.FormData.label: "Menu icon:"
            text: cfg_menuIcon
            readOnly: true

            rightActions: [
                Kirigami.Action {
                    icon.name: "document-open"
                    onTriggered: iconDialog.open()
                }
            ]
        }

        KIconThemes.IconDialog {
            id: iconDialog
            onIconNameChanged: iconButton.currentIcon = iconName
        }

        QQC2.Button {
            id: iconButton
            property string currentIcon: Plasmoid.configuration.menuIcon

            icon.name: currentIcon
            text: "Choose..."
            onClicked: iconDialog.open()
        }
    }
}
