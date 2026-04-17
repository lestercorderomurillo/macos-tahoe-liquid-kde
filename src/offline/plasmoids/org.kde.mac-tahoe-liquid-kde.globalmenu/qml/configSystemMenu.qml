/*
    SPDX-License-Identifier: GPL-2.0-or-later
*/
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM
import org.kde.iconthemes as KIconThemes
import org.kde.plasma.plasmoid

KCM.SimpleKCM {
    id: configSystemMenu

    property alias cfg_menuIcon:         iconButton.currentIcon
    property alias cfg_useSystemFont:    useSystemFontCheck.checked
    property alias cfg_iconAbout:          iconAboutField.text
    property alias cfg_iconSystemSettings: iconSystemSettingsField.text
    property alias cfg_iconAppStore:       iconAppStoreField.text
    property alias cfg_iconForceQuit:      iconForceQuitField.text
    property alias cfg_iconSleep:          iconSleepField.text
    property alias cfg_iconRestart:        iconRestartField.text
    property alias cfg_iconShutDown:       iconShutDownField.text
    property alias cfg_iconLockScreen:     iconLockScreenField.text
    property alias cfg_iconLogOut:         iconLogOutField.text
    property alias cfg_cmdSleep:         cmdSleepField.text
    property alias cfg_cmdRestart:       cmdRestartField.text
    property alias cfg_cmdShutDown:      cmdShutDownField.text
    property alias cfg_cmdLockScreen:    cmdLockScreenField.text
    property alias cfg_cmdLogOut:        cmdLogOutField.text

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

        // ── Appearance ────────────────────────────────────────────
        Kirigami.Separator {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: "Appearance"
        }

        QQC2.CheckBox {
            id: useSystemFontCheck
            Kirigami.FormData.label: "About window:"
            text: "Use system font instead of SF Pro"
            checked: Plasmoid.configuration.useSystemFont
        }

        // ── Icons ─────────────────────────────────────────────────
        Kirigami.Separator {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: "Menu Item Icons"
        }

        Kirigami.ActionTextField {
            id: iconAboutField
            Kirigami.FormData.label: "About This Computer:"
            text: Plasmoid.configuration.iconAbout
            rightActions: [ Kirigami.Action { icon.name: "document-open"; onTriggered: { iconAboutDialog.open() } } ]
        }
        KIconThemes.IconDialog { id: iconAboutDialog; onIconNameChanged: iconAboutField.text = iconName }

        Kirigami.ActionTextField {
            id: iconSystemSettingsField
            Kirigami.FormData.label: "System Settings:"
            text: Plasmoid.configuration.iconSystemSettings
            rightActions: [ Kirigami.Action { icon.name: "document-open"; onTriggered: { iconSystemSettingsDialog.open() } } ]
        }
        KIconThemes.IconDialog { id: iconSystemSettingsDialog; onIconNameChanged: iconSystemSettingsField.text = iconName }

        Kirigami.ActionTextField {
            id: iconAppStoreField
            Kirigami.FormData.label: "App Store:"
            text: Plasmoid.configuration.iconAppStore
            rightActions: [ Kirigami.Action { icon.name: "document-open"; onTriggered: { iconAppStoreDialog.open() } } ]
        }
        KIconThemes.IconDialog { id: iconAppStoreDialog; onIconNameChanged: iconAppStoreField.text = iconName }

        Kirigami.ActionTextField {
            id: iconForceQuitField
            Kirigami.FormData.label: "Force Quit:"
            text: Plasmoid.configuration.iconForceQuit
            rightActions: [ Kirigami.Action { icon.name: "document-open"; onTriggered: { iconForceQuitDialog.open() } } ]
        }
        KIconThemes.IconDialog { id: iconForceQuitDialog; onIconNameChanged: iconForceQuitField.text = iconName }

        Kirigami.ActionTextField {
            id: iconSleepField
            Kirigami.FormData.label: "Sleep:"
            text: Plasmoid.configuration.iconSleep
            rightActions: [ Kirigami.Action { icon.name: "document-open"; onTriggered: { iconSleepDialog.open() } } ]
        }
        KIconThemes.IconDialog { id: iconSleepDialog; onIconNameChanged: iconSleepField.text = iconName }

        Kirigami.ActionTextField {
            id: iconRestartField
            Kirigami.FormData.label: "Restart:"
            text: Plasmoid.configuration.iconRestart
            rightActions: [ Kirigami.Action { icon.name: "document-open"; onTriggered: { iconRestartDialog.open() } } ]
        }
        KIconThemes.IconDialog { id: iconRestartDialog; onIconNameChanged: iconRestartField.text = iconName }

        Kirigami.ActionTextField {
            id: iconShutDownField
            Kirigami.FormData.label: "Shut Down:"
            text: Plasmoid.configuration.iconShutDown
            rightActions: [ Kirigami.Action { icon.name: "document-open"; onTriggered: { iconShutDownDialog.open() } } ]
        }
        KIconThemes.IconDialog { id: iconShutDownDialog; onIconNameChanged: iconShutDownField.text = iconName }

        Kirigami.ActionTextField {
            id: iconLockScreenField
            Kirigami.FormData.label: "Lock Screen:"
            text: Plasmoid.configuration.iconLockScreen
            rightActions: [ Kirigami.Action { icon.name: "document-open"; onTriggered: { iconLockScreenDialog.open() } } ]
        }
        KIconThemes.IconDialog { id: iconLockScreenDialog; onIconNameChanged: iconLockScreenField.text = iconName }

        Kirigami.ActionTextField {
            id: iconLogOutField
            Kirigami.FormData.label: "Log Out:"
            text: Plasmoid.configuration.iconLogOut
            rightActions: [ Kirigami.Action { icon.name: "document-open"; onTriggered: { iconLogOutDialog.open() } } ]
        }
        KIconThemes.IconDialog { id: iconLogOutDialog; onIconNameChanged: iconLogOutField.text = iconName }

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
