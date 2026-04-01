/*
    Kpple Menu — macOS-style system menu for the top panel.
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
    hideOnWindowDeactivate: true

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
            separator: false,
            action: function() {
                executable.exec("kinfocenter");
            }
        },
        { separator: true },
        {
            text: "System Settings...",
            separator: false,
            action: function() {
                executable.exec("systemsettings");
            }
        },
        {
            text: "App Store...",
            separator: false,
            action: function() {
                executable.exec("plasma-discover");
            }
        },
        { separator: true },
        {
            text: "Force Quit...",
            separator: false,
            action: function() {
                // qdbus6 slotKillWindow works on Wayland; xkill is the X11 fallback
                executable.exec("qdbus6 org.kde.KWin /KWin slotKillWindow || xkill");
            }
        },
        { separator: true },
        {
            text: "Sleep",
            separator: false,
            action: function() {
                executable.exec(Plasmoid.configuration.cmdSleep);
            }
        },
        {
            text: "Restart...",
            separator: false,
            action: function() {
                executable.exec(Plasmoid.configuration.cmdRestart);
            }
        },
        {
            text: "Shut Down...",
            separator: false,
            action: function() {
                executable.exec(Plasmoid.configuration.cmdShutDown);
            }
        },
        { separator: true },
        {
            text: "Lock Screen",
            separator: false,
            action: function() {
                executable.exec(Plasmoid.configuration.cmdLockScreen);
            }
        },
        {
            text: "Log Out...",
            separator: false,
            action: function() {
                executable.exec(Plasmoid.configuration.cmdLogOut);
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

    // ── full: the dropdown menu ───────────────────────────────��─────
    fullRepresentation: Item {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 16
        Layout.maximumWidth: Kirigami.Units.gridUnit * 16
        Layout.minimumWidth: Kirigami.Units.gridUnit * 16
        Layout.preferredHeight: menuColumn.implicitHeight + Kirigami.Units.gridUnit
        Layout.maximumHeight: menuColumn.implicitHeight + Kirigami.Units.gridUnit
        Layout.minimumHeight: menuColumn.implicitHeight + Kirigami.Units.gridUnit

        ColumnLayout {
            id: menuColumn
            anchors {
                fill: parent
                topMargin: Kirigami.Units.smallSpacing * 2
                bottomMargin: Kirigami.Units.smallSpacing * 2
                leftMargin: Kirigami.Units.smallSpacing
                rightMargin: Kirigami.Units.smallSpacing
            }
            spacing: Kirigami.Units.smallSpacing

            Repeater {
                model: root.menuActions

                delegate: Item {
                    id: delegateItem
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: modelData.separator ? sep.height + Kirigami.Units.smallSpacing * 2 : btn.implicitHeight

                    Kirigami.Separator {
                        id: sep
                        visible: delegateItem.modelData.separator === true
                        anchors {
                            left: parent.left; right: parent.right
                            leftMargin: Kirigami.Units.smallSpacing
                            rightMargin: Kirigami.Units.smallSpacing
                        }
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    QQC2.ItemDelegate {
                        id: btn
                        visible: delegateItem.modelData.separator !== true
                        anchors { left: parent.left; right: parent.right }
                        text: delegateItem.modelData.text || ""
                        topPadding: Kirigami.Units.smallSpacing * 1.5
                        bottomPadding: Kirigami.Units.smallSpacing * 1.5
                        leftPadding: Kirigami.Units.largeSpacing
                        rightPadding: Kirigami.Units.largeSpacing

                        background: Rectangle {
                            radius: Kirigami.Units.cornerRadius
                            color: btn.hovered ? Kirigami.Theme.highlightColor : "transparent"
                        }

                        contentItem: Text {
                            text: btn.text
                            color: btn.hovered ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                            font: btn.font
                            verticalAlignment: Text.AlignVCenter
                        }

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
