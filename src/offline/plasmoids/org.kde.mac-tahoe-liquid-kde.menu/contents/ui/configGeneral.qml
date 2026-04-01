import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM
import org.kde.iconthemes as KIconThemes
import org.kde.plasma.plasmoid

KCM.SimpleKCM {
    id: configGeneral

    property alias cfg_menuIcon:     iconButton.currentIcon
    property alias cfg_cmdSleep:     cmdSleepField.text
    property alias cfg_cmdRestart:   cmdRestartField.text
    property alias cfg_cmdShutDown:  cmdShutDownField.text
    property alias cfg_cmdLockScreen: cmdLockScreenField.text
    property alias cfg_cmdLogOut:    cmdLogOutField.text

    Kirigami.FormLayout {

        // ── Icon ─────────────────────────────────────────────────
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

        // ── Commands ──────────────────────────────────────────────
        Kirigami.Separator {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: "Commands"
        }

        QQC2.TextField {
            id: cmdSleepField
            Kirigami.FormData.label: "Sleep:"
            text: Plasmoid.configuration.cmdSleep
            Layout.fillWidth: true
        }

        QQC2.TextField {
            id: cmdRestartField
            Kirigami.FormData.label: "Restart:"
            text: Plasmoid.configuration.cmdRestart
            Layout.fillWidth: true
        }

        QQC2.TextField {
            id: cmdShutDownField
            Kirigami.FormData.label: "Shut Down:"
            text: Plasmoid.configuration.cmdShutDown
            Layout.fillWidth: true
        }

        QQC2.TextField {
            id: cmdLockScreenField
            Kirigami.FormData.label: "Lock Screen:"
            text: Plasmoid.configuration.cmdLockScreen
            Layout.fillWidth: true
        }

        QQC2.TextField {
            id: cmdLogOutField
            Kirigami.FormData.label: "Log Out:"
            text: Plasmoid.configuration.cmdLogOut
            Layout.fillWidth: true
        }
    }
}
