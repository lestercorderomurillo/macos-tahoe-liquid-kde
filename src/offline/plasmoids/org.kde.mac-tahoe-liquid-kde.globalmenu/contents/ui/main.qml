/*
    MacTahoe Liquid KDE — App Menu plasmoid.
    Configurable drop-down menu for the top panel: items and commands are
    fully editable from the widget settings (JSON-based model).

    Forked from com.github.edmogeor.kppleMenu (GPL-2.0-or-later).
    Original authors: Kpple <info.kpple@gmail.com>,
                      Christian Tallner <chrtall@gmx.de>

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    toolTipMainText: Plasmoid.configuration.toolTipTitle
    toolTipSubText: Plasmoid.configuration.toolTipSubText
    hideOnWindowDeactivate: true
    Plasmoid.icon: Plasmoid.configuration.icon
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground

    preferredRepresentation: compactRepresentation

    property bool fullRepHasFocus: false

    property var menuItemsModel: {
        try {
            return JSON.parse(Plasmoid.configuration.menuItems)
        } catch (e) {
            console.error("App Menu: failed to parse menuItems:", e)
            return []
        }
    }

    // ── command runner ───────────────────────────────────────────────
    Plasma5Support.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []
        property var callbacks: ({})

        onNewData: (sourceName, data) => {
            var stdout = data["stdout"]
            if (callbacks[sourceName] !== undefined) {
                callbacks[sourceName](stdout)
            }
            exited(sourceName, stdout)
            disconnectSource(sourceName)
        }

        function exec(cmd, onNewDataCallback) {
            root.expanded = false
            if (onNewDataCallback !== undefined) {
                callbacks[cmd] = onNewDataCallback
            }
            connectSource(cmd)
        }
        signal exited(string sourceName, string stdout)
    }

    onExpandedChanged: (expanded) => {
        root.fullRepHasFocus = expanded
    }

    // ── compact: icon button (same sizing as menu plasmoid) ──────────
    compactRepresentation: Item {
        id: compactTile

        Layout.minimumWidth:  Math.round(parent.height * 2.275) - 4
        Layout.preferredWidth: Math.round(parent.height * 2.275) - 4

        MouseArea {
            id: compactRoot
            anchors.fill: parent
            hoverEnabled: true
            onClicked: root.expanded = !root.expanded
        }

        Kirigami.Icon {
            anchors.centerIn: parent
            width:  Math.round(compactTile.height * 0.924) + 4
            height: Math.round(compactTile.height * 0.924) + 4
            source: Plasmoid.configuration.icon || "start-here-kde-symbolic"
            active: compactRoot.containsMouse
        }
    }

    // ── full: the dropdown menu ──────────────────────────────────────
    fullRepresentation: Item {
        id: fullRep

        readonly property double iwSize: Kirigami.Units.gridUnit * 12.6
        readonly property double shSize: 1.1

        Layout.preferredWidth: iwSize
        Layout.preferredHeight: columnLayout.implicitHeight
        Layout.minimumHeight: columnLayout.implicitHeight

        focus: root.fullRepHasFocus
        Keys.onPressed: (event) => {
            var firstItem = null
            var lastItem = null
            for (var i = 0; i < menuRepeater.count; i++) {
                var loader = menuRepeater.itemAt(i)
                if (loader && loader.isMenuItem && loader.item) {
                    if (!firstItem) firstItem = loader.item
                    lastItem = loader.item
                }
            }
            switch (event.key) {
                case Qt.Key_Up:
                    if (lastItem) lastItem.forceActiveFocus()
                    break
                case Qt.Key_Down:
                    if (firstItem) firstItem.forceActiveFocus()
                    break
            }
        }

        ColumnLayout {
            id: columnLayout
            anchors.fill: parent
            spacing: 2

            Repeater {
                id: menuRepeater
                model: root.menuItemsModel

                delegate: Loader {
                    id: delegateLoader
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true

                    property bool isMenuItem: modelData.type === "item"
                    property int itemIndex: index

                    sourceComponent: modelData.type === "divider" ? dividerComponent : menuItemComponent

                    function forceActiveFocus() {
                        if (item && item.forceActiveFocus) item.forceActiveFocus()
                    }

                    Component {
                        id: dividerComponent
                        MenuSeparator {
                            padding: 0
                            topPadding: 5
                            bottomPadding: 5
                            contentItem: Rectangle {
                                implicitWidth: fullRep.iwSize
                                implicitHeight: fullRep.shSize
                                color: "#1E000000"
                            }
                        }
                    }

                    Component {
                        id: menuItemComponent
                        ListDelegate {
                            id: menuItem
                            text: delegateLoader.modelData.name || ""

                            PlasmaComponents.Label {
                                visible: delegateLoader.modelData.shortcut ? true : false
                                text: delegateLoader.modelData.shortcut ? delegateLoader.modelData.shortcut + " " : ""
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            onClicked: {
                                if (delegateLoader.modelData.command) {
                                    executable.exec(delegateLoader.modelData.command)
                                }
                            }

                            activeFocusOnTab: true

                            KeyNavigation.up: {
                                for (var i = delegateLoader.itemIndex - 1; i >= 0; i--) {
                                    var l = menuRepeater.itemAt(i)
                                    if (l && l.isMenuItem && l.item) return l.item
                                }
                                for (var j = menuRepeater.count - 1; j > delegateLoader.itemIndex; j--) {
                                    var l2 = menuRepeater.itemAt(j)
                                    if (l2 && l2.isMenuItem && l2.item) return l2.item
                                }
                                return null
                            }

                            KeyNavigation.down: {
                                for (var i = delegateLoader.itemIndex + 1; i < menuRepeater.count; i++) {
                                    var l = menuRepeater.itemAt(i)
                                    if (l && l.isMenuItem && l.item) return l.item
                                }
                                for (var j = 0; j < delegateLoader.itemIndex; j++) {
                                    var l2 = menuRepeater.itemAt(j)
                                    if (l2 && l2.isMenuItem && l2.item) return l2.item
                                }
                                return null
                            }
                        }
                    }
                }
            }
        }
    }
}
