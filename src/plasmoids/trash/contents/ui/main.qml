/*
    SPDX-FileCopyrightText: 2013 Heena Mahour <heena393@gmail.com>
    SPDX-FileCopyrightText: 2015, 2016 Kai Uwe Broulik <kde@privat.broulik.de>
    SPDX-FileCopyrightText: 2023 Nate Graham <nate@kde.org>
    SPDX-FileCopyrightText: 2025 MacTahoe Liquid KDE

    SPDX-License-Identifier: GPL-2.0-or-later

    Forked from org.kde.plasma.trash (Plasma 6) to support customizable icons.
*/
pragma ComponentBehavior: Bound

import QtQuick

import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.extras as PlasmaExtras
import org.kde.draganddrop as DragDrop
import org.kde.kirigami as Kirigami

import org.kde.kcmutils as KCM
import org.kde.config as KConfig

PlasmoidItem {
    id: root

    readonly property bool inPanel: (Plasmoid.location === PlasmaCore.Types.TopEdge
        || Plasmoid.location === PlasmaCore.Types.RightEdge
        || Plasmoid.location === PlasmaCore.Types.BottomEdge
        || Plasmoid.location === PlasmaCore.Types.LeftEdge)

    property int trashCount: 0
    readonly property bool hasContents: trashCount > 0
    property bool containsAcceptableDrag: false

    readonly property string iconEmpty: Plasmoid.configuration.iconEmpty || "user-trash"
    readonly property string iconFull: Plasmoid.configuration.iconFull || "user-trash-full"

    Plasmoid.title: i18nc("@title the name of the Trash widget", "Trash")
    toolTipSubText: {
        if (hasContents) {
            return i18ncp("@info:status", "One item", "%1 items", trashCount);
        } else {
            return i18nc("@info:status The trash is empty", "Empty");
        }
    }

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: {
        let iconName = hasContents ? iconFull : iconEmpty;
        if (inPanel && !iconName.endsWith("-symbolic")) {
            iconName += "-symbolic";
        }
        return iconName;
    }
    Plasmoid.status: hasContents ? PlasmaCore.Types.ActiveStatus : PlasmaCore.Types.PassiveStatus

    Plasmoid.onActivated: openTrash()

    function openTrash() {
        executable.exec("xdg-open trash:///");
    }

    function emptyTrash() {
        executable.exec("qdbus6 org.kde.ktrash6 /KTrash emptyTrash");
    }

    // -- Executable helper ------------------------------------------------
    PlasmaCore.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source);
        }
        function exec(cmd: string) {
            connectSource(cmd);
        }
    }

    // -- Trash directory monitor ------------------------------------------
    PlasmaCore.DataSource {
        id: trashMonitor
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            root.trashCount = parseInt(data["stdout"].trim()) || 0;
            disconnectSource(source);
        }
    }

    Timer {
        id: pollTimer
        interval: 5000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            trashMonitor.connectSource(
                "ls -A \"$HOME/.local/share/Trash/files\" 2>/dev/null | wc -l"
            );
        }
    }

    // -- Keyboard ---------------------------------------------------------
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

    // -- Context menu -----------------------------------------------------
    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            text: i18nc("@action:inmenu Open the trash", "Open")
            icon.name: "document-open-symbolic"
            onTriggered: root.openTrash()
        },
        PlasmaCore.Action {
            text: i18nc("@action:inmenu Empty the trash", "Empty Trash")
            icon.name: "trash-empty-symbolic"
            enabled: root.hasContents
            onTriggered: root.emptyTrash()
        },
        PlasmaCore.Action {
            text: i18nc("@action:inmenu", "Trash Settings…")
            icon.name: "configure-symbolic"
            visible: KConfig.KAuthorized.authorizeControlModule("kcm_trash")
            onTriggered: KCM.KCMLauncher.open("kcm_trash")
        }
    ]

    // -- Visual representation --------------------------------------------
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
                if (event.mimeData.urls && event.mimeData.urls.length > 0) {
                    root.containsAcceptableDrag = true;
                    event.accept(Qt.MoveAction);
                }
            }
            onDragLeave: root.containsAcceptableDrag = false

            onDrop: event => {
                root.containsAcceptableDrag = false;
                var urls = event.mimeData.urls;
                if (urls && urls.length > 0) {
                    for (var i = 0; i < urls.length; i++) {
                        executable.exec("gio trash '" + urls[i] + "'");
                    }
                    event.accept(Qt.MoveAction);
                    // refresh count immediately
                    pollTimer.restart();
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
