/*
    Kpple Menu — macOS-style Apple Menu for the top panel.
    Shows system actions: About, System Settings, Sleep, Restart,
    Shut Down, Lock Screen, Log Out.

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2

import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5Support

PlasmoidItem {
    id: root

    readonly property string cfgIcon: Plasmoid.configuration.menuIcon || "start-here-kde-symbolic"

    Plasmoid.title: "Menu"
    Plasmoid.icon: cfgIcon
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground

    switchWidth: Kirigami.Units.gridUnit * 14
    switchHeight: Kirigami.Units.gridUnit * 18

    preferredRepresentation: compactRepresentation

    // ── command runner ───────────────────────────────────────────────
    P5Support.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []

        onNewData: (sourceName, data) => {
            disconnectSource(sourceName);
        }

        function exec(cmd: string): void {
            connectSource(cmd);
        }
    }

    // ── actions ─────────────────────────────────────────────────────
    readonly property var menuActions: [
        {
            text: "About This Computer",
            icon: "help-about-symbolic",
            separator: false,
            action: function() {
                executable.exec("kinfocenter");
            }
        },
        { separator: true },
        {
            text: "System Settings...",
            icon: "preferences-system-symbolic",
            separator: false,
            action: function() {
                executable.exec("systemsettings");
            }
        },
        { separator: true },
        {
            text: "Sleep",
            icon: "system-suspend-symbolic",
            separator: false,
            action: function() {
                executable.exec("systemctl suspend");
            }
        },
        {
            text: "Restart...",
            icon: "system-reboot-symbolic",
            separator: false,
            action: function() {
                executable.exec("qdbus org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptReboot");
            }
        },
        {
            text: "Shut Down...",
            icon: "system-shutdown-symbolic",
            separator: false,
            action: function() {
                executable.exec("qdbus org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptShutDown");
            }
        },
        { separator: true },
        {
            text: "Lock Screen",
            icon: "system-lock-screen-symbolic",
            separator: false,
            action: function() {
                executable.exec("loginctl lock-session");
            }
        },
        {
            text: "Log Out...",
            icon: "system-log-out-symbolic",
            separator: false,
            action: function() {
                executable.exec("qdbus org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptLogout");
            }
        }
    ]

    // ── compact: just the icon ──────────────────────────────────────
    compactRepresentation: MouseArea {
        id: compactRoot

        hoverEnabled: true
        onClicked: root.expanded = !root.expanded

        Kirigami.Icon {
            anchors.fill: parent
            source: root.cfgIcon
            active: compactRoot.containsMouse
        }
    }

    // ── full: the dropdown menu ─────────────────────────────────────
    fullRepresentation: Item {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 16
        Layout.preferredHeight: menuColumn.implicitHeight + Kirigami.Units.largeSpacing * 2

        ColumnLayout {
            id: menuColumn
            anchors {
                fill: parent
                margins: Kirigami.Units.largeSpacing
            }
            spacing: 0

            Repeater {
                model: root.menuActions

                delegate: Item {
                    id: delegateItem
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: modelData.separator ? sep.implicitHeight : btn.implicitHeight

                    Kirigami.Separator {
                        id: sep
                        visible: delegateItem.modelData.separator === true
                        anchors { left: parent.left; right: parent.right }
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    QQC2.ItemDelegate {
                        id: btn
                        visible: delegateItem.modelData.separator !== true
                        anchors { left: parent.left; right: parent.right }
                        text: delegateItem.modelData.text || ""
                        icon.name: delegateItem.modelData.icon || ""
                        onClicked: {
                            delegateItem.modelData.action();
                            root.expanded = false;
                        }
                    }
                }
            }
        }
    }
}
