/*
    Fork: MacTahoe Liquid KDE — adds configurable empty/full icons.
    Replaces compiled C++ backend with shell commands so no build step
    is needed.

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick

import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.extras as PlasmaExtras
import org.kde.draganddrop as DragDrop
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5Support

PlasmoidItem {
    id: root

    readonly property bool inPanel: (Plasmoid.location === PlasmaCore.Types.TopEdge
        || Plasmoid.location === PlasmaCore.Types.RightEdge
        || Plasmoid.location === PlasmaCore.Types.BottomEdge
        || Plasmoid.location === PlasmaCore.Types.LeftEdge)

    readonly property string cfgEmptyIcon: Plasmoid.configuration.emptyIcon || "user-trash"
    readonly property string cfgFullIcon: Plasmoid.configuration.fullIcon || "user-trash-full"

    property int trashCount: 0
    readonly property bool hasContents: trashCount > 0
    property bool emptying: false
    property bool containsAcceptableDrag: false

    Plasmoid.title: "Trash"
    toolTipSubText: {
        if (emptying) {
            return "Emptying\u2026";
        } else if (hasContents) {
            return trashCount === 1 ? "One item" : trashCount + " items";
        }
        return "Empty";
    }

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: hasContents ? cfgFullIcon : cfgEmptyIcon
    Plasmoid.status: hasContents ? PlasmaCore.Types.ActiveStatus
                                : PlasmaCore.Types.PassiveStatus
    Plasmoid.busy: emptying

    Plasmoid.onActivated: Qt.openUrlExternally("trash:/")

    // ── trash monitoring (polls every 3 s) ──────────────────────────
    P5Support.DataSource {
        id: trashMonitor
        engine: "executable"
        connectedSources: [cmd]
        interval: 3000

        readonly property string cmd:
            "ls -1A \"$HOME/.local/share/Trash/files/\" 2>/dev/null | wc -l"

        onNewData: (sourceName, data) => {
            if (sourceName === cmd) {
                let n = parseInt(data["stdout"]) || 0;
                if (n !== root.trashCount) {
                    root.trashCount = n;
                }
                if (root.emptying && n === 0) {
                    root.emptying = false;
                }
            }
        }
    }

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

    // ── keyboard ─────────────────────────────────────────────────────
    Keys.onPressed: event => {
        switch (event.key) {
        case Qt.Key_Space:
        case Qt.Key_Enter:
        case Qt.Key_Return:
        case Qt.Key_Select:
            Plasmoid.activated();
            break;
        }
    }
    Accessible.name: Plasmoid.title
    Accessible.description: toolTipSubText
    Accessible.role: Accessible.Button

    // ── context menu ─────────────────────────────────────────────────
    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            text: "Open"
            icon.name: "document-open-symbolic"
            onTriggered: Plasmoid.activated()
        },
        PlasmaCore.Action {
            text: "Empty Trash"
            icon.name: "trash-empty-symbolic"
            enabled: root.hasContents && !root.emptying
            onTriggered: {
                root.emptying = true;
                executable.exec(
                    "kdialog --warningyesno 'Permanently delete all items in the trash?' "
                    + "--title 'Empty Trash' && ktrash6 --empty "
                    + "|| true"
                );
            }
        }
    ]

    // ── representation ───────────────────────────────────────────────
    preferredRepresentation: fullRepresentation
    fullRepresentation: MouseArea {
        id: mouseArea

        activeFocusOnTab: true
        hoverEnabled: true

        onClicked: Plasmoid.activated()

        DragDrop.DropArea {
            anchors.fill: parent
            preventStealing: true

            onDragEnter: event => {
                let dominated = false;
                for (let i = 0; i < event.mimeData.urls.length; i++) {
                    if (event.mimeData.urls[i].toString().startsWith("file://")) {
                        dominated = true;
                        break;
                    }
                }
                root.containsAcceptableDrag = dominated;
            }
            onDragLeave: root.containsAcceptableDrag = false

            onDrop: event => {
                root.containsAcceptableDrag = false;

                let paths = [];
                for (let i = 0; i < event.mimeData.urls.length; i++) {
                    let url = event.mimeData.urls[i].toString();
                    if (url.startsWith("file://")) {
                        let path = decodeURIComponent(url.substring(7));
                        paths.push("'" + path.replace(/'/g, "'\\''") + "'");
                    }
                }

                if (paths.length > 0) {
                    executable.exec("gio trash " + paths.join(" "));
                    event.accept(Qt.MoveAction);
                } else {
                    event.accept(Qt.IgnoreAction);
                }
            }
        }

        Kirigami.Icon {
            source: Plasmoid.icon
            anchors {
                left: parent.left
                right: parent.right
                top: parent.top
                bottom: root.inPanel ? parent.bottom : text.top
            }
            active: mouseArea.containsMouse || root.containsAcceptableDrag
        }

        PlasmaExtras.ShadowedLabel {
            id: text
            anchors {
                horizontalCenter: parent.horizontalCenter
                bottom: parent.bottom
            }
            width: Math.round(text.implicitWidth + Kirigami.Units.smallSpacing)
            text: Plasmoid.title + "\n" + root.toolTipSubText
            horizontalAlignment: Text.AlignHCenter
            visible: !root.inPanel
        }

        PlasmaCore.ToolTipArea {
            anchors.fill: parent
            mainText: Plasmoid.title
            subText: root.toolTipSubText
        }
    }
}
