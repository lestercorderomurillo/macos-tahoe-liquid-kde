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
    width: 860
    height: 588
    minimumWidth: 860
    minimumHeight: 588
    maximumWidth: 860
    maximumHeight: 588
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

        // ── flat squircle button (macOS-style, no accent, no gradient) ────
        // White in light theme / dark grey in dark theme. The colour does
        // NOT react to hover (that flickered as the cursor crossed button
        // edges) and has no Behavior animation — only the pressed state
        // swaps colour, instantly. hoverEnabled stays on so the gear's
        // tooltip still works; it just no longer drives the background.
        component FlatButton: QQC2.Button {
            id: flatBtn

            readonly property color baseColor: installerWindow.isDarkTheme
                ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(1, 1, 1, 1.0)
            readonly property color pressColor: installerWindow.isDarkTheme
                ? Qt.rgba(1, 1, 1, 0.22) : Qt.rgba(0, 0, 0, 0.09)

            implicitHeight: 40
            leftPadding: 22
            rightPadding: 22
            font.family: installerWindow.fontFamily
            font.pointSize: Kirigami.Theme.defaultFont.pointSize
            font.weight: Font.DemiBold
            enabled: !installerWindow.busy

            background: Rectangle {
                radius: 13
                color: flatBtn.down ? flatBtn.pressColor : flatBtn.baseColor
                border.width: 1
                border.color: installerWindow.isDarkTheme
                    ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(0, 0, 0, 0.13)
            }

            contentItem: Text {
                text: flatBtn.text
                font: flatBtn.font
                color: Kirigami.Theme.textColor
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }

        // ── main view ────────────────────────────────────────────────────
        ColumnLayout {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: bottomBar.top
            anchors.leftMargin: 24
            anchors.rightMargin: 24
            anchors.topMargin: 52
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

            Item { Layout.fillHeight: true }
        }

        // ── bottom toolbar (macOS-style action bar) ───────────────────────
        // Pinned to the window bottom with a hairline divider above it.
        // Buttons are centered. Only shown in the main view; the
        // installing/success views own the full glass area.
        Item {
            id: bottomBar
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 88
            visible: installerWindow.viewMode === "main"

            // Solid (not glass) bar: full white in light theme, full dark
            // in dark theme. Only the two BOTTOM corners are rounded (to
            // match the window). A Rectangle can't round individual
            // corners, so: one rounded rect (radius 22) gives the bottom
            // corners, and a square rect over the top half squares off
            // the top — both clipped to the bar, so nothing pokes above
            // the divider. Colours are identical so the seam is invisible.
            readonly property color barColor: installerWindow.isDarkTheme
                ? "#2A2A2E" : "#FFFFFF"

            Rectangle {
                anchors.fill: parent
                radius: 22
                color: bottomBar.barColor
            }
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: parent.height / 2
                color: bottomBar.barColor
            }

            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: installerWindow.isDarkTheme
                    ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(0, 0, 0, 0.08)
            }

            RowLayout {
                anchors.centerIn: parent
                spacing: 10

                FlatButton {
                    text: "Install"
                    onClicked: installerWindow.runAction("install")
                }

                FlatButton {
                    text: "Uninstall"
                    onClicked: installerWindow.runAction("uninstall")
                }

                FlatButton {
                    id: gearButton
                    leftPadding: 0
                    rightPadding: 0
                    implicitWidth: 46
                    QQC2.ToolTip.text: "Features..."
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.delay: 400
                    onClicked: featuresLoader.open()

                    contentItem: Item {
                        Image {
                            id: gearImg
                            anchors.centerIn: parent
                            width: 18
                            height: 18
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
