/*
    Kpple Menu — macOS-style system menu for the top panel.
    Shows system actions: About, System Settings, Sleep, Restart,
    Shut Down, Lock Screen, Log Out.

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
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
    // Proportions derived from macOS Tahoe menu bar:
    //   tile width  ≈ 1.75 × panel height  (e.g. 77 px at 44 px panel)
    //   icon size   ≈ 0.60 × panel height  (e.g. 26 px at 44 px panel)
    compactRepresentation: Item {
        id: compactTile

        Layout.minimumWidth:  Math.round(parent.height * 2.275) - 4
        Layout.preferredWidth: Math.round(parent.height * 2.275) - 4

        // Walk up to the panel applet container so the tile can
        // extend to the full panel height (negative margins).
        readonly property var containerMargins: {
            let item = compactTile;
            while (item.parent) {
                item = item.parent;
                if (item.isAppletContainer) {
                    return item.getMargins;
                }
            }
            return undefined;
        }

        MouseArea {
            id: compactRoot
            anchors.fill: parent
            hoverEnabled: true
            onClicked: root.expanded = !root.expanded
        }

        Rectangle {
            anchors {
                fill: parent
                topMargin:    compactTile.containerMargins ? -compactTile.containerMargins('top', true) : 0
                bottomMargin: compactTile.containerMargins ? -compactTile.containerMargins('bottom', true) : 0
            }
            radius: Kirigami.Units.cornerRadius
            color: (compactRoot.containsMouse || compactRoot.containsPress || root.expanded)
                   ? Qt.rgba(0.5, 0.5, 0.5, 0.18) : "transparent"
        }

        Kirigami.Icon {
            anchors.centerIn: parent
            width:  Math.round(compactTile.height * 0.924) + 4
            height: Math.round(compactTile.height * 0.924) + 4
            source: root.cfgIcon
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
                    implicitHeight: modelData.separator
                        ? sep.implicitHeight + Kirigami.Units.smallSpacing * 2
                        : Kirigami.Units.gridUnit * 1.75

                    // ── separator ───────────────────────────────────────
                    Kirigami.Separator {
                        id: sep
                        visible: delegateItem.modelData.separator === true
                        anchors {
                            left: parent.left; right: parent.right
                            leftMargin: Kirigami.Units.smallSpacing
                            rightMargin: Kirigami.Units.smallSpacing
                            verticalCenter: parent.verticalCenter
                        }
                    }

                    // ── menu row ────────────────────────────────────────
                    Item {
                        id: btn
                        visible: !delegateItem.modelData.separator
                        anchors.fill: parent

                        Rectangle {
                            anchors.fill: parent
                            radius: Kirigami.Units.cornerRadius
                            color: (ma.containsMouse || ma.containsPress)
                                   ? Kirigami.Theme.highlightColor : "transparent"
                        }

                        Text {
                            anchors {
                                fill: parent
                                leftMargin: Kirigami.Units.largeSpacing
                                rightMargin: Kirigami.Units.largeSpacing
                            }
                            text: delegateItem.modelData.text || ""
                            color: (ma.containsMouse || ma.containsPress)
                                   ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                            font: Kirigami.Theme.defaultFont
                            verticalAlignment: Text.AlignVCenter
                        }

                        MouseArea {
                            id: ma
                            anchors.fill: parent
                            hoverEnabled: true
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
}
