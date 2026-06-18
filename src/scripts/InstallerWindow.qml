/*
    Thin wrapper UI for the existing installer commands.

    This window intentionally does not implement install logic itself.
    It launches ``sudo ./install`` / ``sudo ./uninstall`` in a terminal
    so the current Python backend, sudo flow, and logging stay intact.

    Run directly with:
        python3 src/scripts/installer_ui.py

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtQuick.Window

import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5Support

Window {
    id: installerWindow

    // "main" → buttons + logo
    // "installing" → centered spinner + current step
    // "success" → checkmark + "Installed!" (auto-returns to "main")
    property string viewMode: "main"
    property string currentAction: ""

    readonly property bool busy: viewMode === "installing"
    readonly property string fontFamily: Kirigami.Theme.defaultFont.family
    readonly property string launcherScriptPath: _localPath(Qt.resolvedUrl("installer_ui.py"))
    readonly property bool isDarkTheme: {
        const bg = Kirigami.Theme.backgroundColor;
        return (bg.r * 0.299 + bg.g * 0.587 + bg.b * 0.114) < 0.5;
    }

    title: "MacTahoe Liquid KDE Installer"
    width: 760
    height: 520
    minimumWidth: 760
    minimumHeight: 520
    maximumWidth: 760
    maximumHeight: 520
    flags: Qt.Window | Qt.FramelessWindowHint
    color: "transparent"

    Component.onCompleted: {
        const s = Screen;
        x = Math.round((s.width - width) / 2);
        y = Math.round((s.height - height) / 2);
    }

    function _localPath(url: url): string {
        const text = url.toString();
        if (text.startsWith("file://"))
            return decodeURIComponent(text.slice(7));
        return text;
    }

    function runAction(action: string): void {
        if (!installer) {
            console.warn("installer bridge missing — running without PyQt6?");
            return;
        }
        currentAction = action;
        viewMode = "installing";
        installer.start(action);
    }

    Connections {
        target: installer ? installer : null
        function onFinished(code) {
            if (code === 0) {
                installerWindow.viewMode = "success";
                successResetTimer.restart();
            } else {
                errorLoader.open(installer.logTail(),
                                 installerWindow.currentAction);
                installerWindow.viewMode = "main";
            }
        }
    }

    Timer {
        id: successResetTimer
        interval: 2000
        onTriggered: installerWindow.viewMode = "main"
    }

    Rectangle {
        id: glass
        anchors.fill: parent
        radius: 22
        color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                       Kirigami.Theme.backgroundColor.g,
                       Kirigami.Theme.backgroundColor.b, 0.82)
        border.width: 0.5
        border.color: installerWindow.isDarkTheme
            ? Qt.rgba(1, 1, 1, 0.12)
            : Qt.rgba(0, 0, 0, 0.10)
        layer.enabled: true

        MouseArea {
            anchors.fill: parent
            property point clickPos: Qt.point(0, 0)
            onPressed: (mouse) => { clickPos = Qt.point(mouse.x, mouse.y) }
            onPositionChanged: (mouse) => {
                installerWindow.x += mouse.x - clickPos.x;
                installerWindow.y += mouse.y - clickPos.y;
            }
        }

        Row {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.leftMargin: 14
            anchors.topMargin: 14
            spacing: 8
            z: 1

            readonly property color inactiveColor: installerWindow.isDarkTheme
                ? Qt.rgba(1, 1, 1, 0.2) : Qt.rgba(0, 0, 0, 0.12)
            readonly property color inactiveBorder: installerWindow.isDarkTheme
                ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.06)

            Rectangle {
                width: 14
                height: 14
                radius: 7
                color: (installerWindow.active && !installerWindow.busy)
                    ? "#FF5F57" : parent.inactiveColor
                border.width: 0.5
                border.color: (installerWindow.active && !installerWindow.busy)
                    ? Qt.rgba(0, 0, 0, 0.12)
                    : parent.inactiveBorder
                Behavior on color { ColorAnimation { duration: 150 } }

                HoverHandler { id: closeHover }
                Text {
                    anchors.centerIn: parent
                    text: "×"
                    color: Qt.rgba(0, 0, 0, 0.5)
                    font.family: installerWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.95
                    font.weight: Font.Bold
                    opacity: closeHover.hovered && installerWindow.active
                        && !installerWindow.busy ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 120 } }
                }
                TapHandler {
                    enabled: !installerWindow.busy
                    onTapped: installerWindow.close()
                }
            }

            Rectangle {
                width: 14
                height: 14
                radius: 7
                color: parent.inactiveColor
                border.width: 0.5
                border.color: parent.inactiveBorder
            }

            Rectangle {
                width: 14
                height: 14
                radius: 7
                color: parent.inactiveColor
                border.width: 0.5
                border.color: parent.inactiveBorder
            }
        }

        // ── main view ────────────────────────────────────────────────────
        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: 24
            anchors.rightMargin: 24
            anchors.topMargin: 52
            anchors.bottomMargin: 24
            spacing: 0
            visible: installerWindow.viewMode === "main"

            Item { Layout.fillHeight: true }

            Image {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 560
                Layout.preferredHeight: 252
                source: "InstallerHello.png"
                fillMode: Image.PreserveAspectFit
                sourceSize.width: 1120
                sourceSize.height: 504
                smooth: true
                mipmap: true
            }

            Item { Layout.preferredHeight: 28 }

            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: 8

                QQC2.Button {
                    text: "Install"
                    onClicked: installerWindow.runAction("install")
                }

                QQC2.Button {
                    text: "Uninstall"
                    onClicked: installerWindow.runAction("uninstall")
                }

                QQC2.Button {
                    QQC2.ToolTip.text: "Features..."
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.delay: 400
                    onClicked: featuresLoader.open()

                    contentItem: Item {
                        implicitWidth: 18
                        implicitHeight: 18

                        Image {
                            id: gearImg
                            anchors.fill: parent
                            source: "InstallerGear.svg"
                            sourceSize.width: 36
                            sourceSize.height: 36
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                            visible: false
                        }

                        MultiEffect {
                            anchors.fill: gearImg
                            source: gearImg
                            colorization: 1.0
                            colorizationColor: Kirigami.Theme.textColor
                        }
                    }
                }
            }

            Item { Layout.fillHeight: true }
        }

        // ── installing view ──────────────────────────────────────────────
        Item {
            anchors.fill: parent
            visible: installerWindow.viewMode === "installing"

            Rectangle {
                id: progressTrack
                anchors.centerIn: parent
                width: 360
                height: 8
                radius: height / 2
                color: installerWindow.isDarkTheme ? "#5A5A5E" : "#B0B0B8"

                property real fraction: installer ? installer.progress : 0.0
                Behavior on fraction {
                    NumberAnimation {
                        duration: 600
                        easing.type: Easing.OutCubic
                    }
                }

                Rectangle {
                    id: progressFill
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: Math.max(parent.height, parent.width * progressTrack.fraction)
                    radius: parent.radius
                    color: "#007AFF"
                }
            }
        }

        // ── success view ─────────────────────────────────────────────────
        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: 24
            anchors.rightMargin: 24
            anchors.topMargin: 52
            anchors.bottomMargin: 24
            spacing: 14
            visible: installerWindow.viewMode === "success"

            Item { Layout.fillHeight: true }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "✓"
                color: "#34c759"
                font.pointSize: 72
                font.weight: Font.Bold
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: installerWindow.currentAction === "uninstall"
                    ? "Uninstalled."
                    : "Installed."
                color: Kirigami.Theme.textColor
                font.family: installerWindow.fontFamily
                font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.4
                font.weight: Font.DemiBold
            }

            Item { Layout.fillHeight: true }
        }
    }

    Loader {
        id: featuresLoader
        active: false
        source: "FeaturesWindow.qml"

        function open(): void {
            active = true;
            if (item) {
                item.launcherScriptPath = installerWindow.launcherScriptPath;
                item.visible = true;
                item.raise();
                item.requestActivate();
            }
        }
    }

    Loader {
        id: errorLoader
        active: false
        source: "InstallError.qml"

        function open(logText: string, action: string): void {
            active = true;
            if (item) {
                item.logText = logText;
                item.action = action;
                item.visible = true;
                item.raise();
                item.requestActivate();
            }
        }

        Connections {
            target: errorLoader.item
            ignoreUnknownSignals: true
            function onRetryRequested(action) {
                installerWindow.runAction(action);
            }
        }
    }
}
