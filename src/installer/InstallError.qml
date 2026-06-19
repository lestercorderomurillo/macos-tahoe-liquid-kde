/*
    Third companion window: install/uninstall failure report.

    Opened by InstallerWindow when the install bridge reports a
    non-zero exit code. Shows the last ~200 lines of stripped stdout
    (the bridge already removed ANSI colors) in a scrollable monospace
    box, with Retry and Close buttons.

    Retry re-runs the same action through the bridge; Close just
    dismisses the window — the main installer is still there underneath
    in its idle state and the user can pick a different action.

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtQuick.Window

import org.kde.kirigami as Kirigami

Window {
    id: errorWindow

    property string action: ""
    property string logText: ""

    signal retryRequested(string action)

    readonly property string fontFamily: Kirigami.Theme.defaultFont.family
    readonly property bool isDarkTheme: {
        const bg = Kirigami.Theme.backgroundColor;
        return (bg.r * 0.299 + bg.g * 0.587 + bg.b * 0.114) < 0.5;
    }

    title: "Install Failed"
    width: 720
    height: 520
    minimumWidth: 720
    minimumHeight: 520
    maximumWidth: 720
    maximumHeight: 520
    flags: Qt.Window | Qt.FramelessWindowHint
    color: "transparent"

    Component.onCompleted: {
        const s = Screen;
        x = Math.round((s.width - width) / 2);
        y = Math.round((s.height - height) / 2);
    }

    Rectangle {
        id: glass
        anchors.fill: parent
        radius: 22
        color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                       Kirigami.Theme.backgroundColor.g,
                       Kirigami.Theme.backgroundColor.b, 0.82)
        border.width: 0.5
        border.color: errorWindow.isDarkTheme
            ? Qt.rgba(1, 1, 1, 0.12)
            : Qt.rgba(0, 0, 0, 0.10)
        layer.enabled: true

        MouseArea {
            anchors.fill: parent
            property point clickPos: Qt.point(0, 0)
            onPressed: (mouse) => { clickPos = Qt.point(mouse.x, mouse.y) }
            onPositionChanged: (mouse) => {
                errorWindow.x += mouse.x - clickPos.x;
                errorWindow.y += mouse.y - clickPos.y;
            }
        }

        Row {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.leftMargin: 14
            anchors.topMargin: 14
            spacing: 8
            z: 1

            readonly property color inactiveColor: errorWindow.isDarkTheme
                ? Qt.rgba(1, 1, 1, 0.2) : Qt.rgba(0, 0, 0, 0.12)
            readonly property color inactiveBorder: errorWindow.isDarkTheme
                ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.06)

            Rectangle {
                width: 14
                height: 14
                radius: 7
                color: errorWindow.active ? "#FF5F57" : parent.inactiveColor
                border.width: 0.5
                border.color: errorWindow.active
                    ? Qt.rgba(0, 0, 0, 0.12)
                    : parent.inactiveBorder

                HoverHandler { id: closeHover }
                Text {
                    anchors.centerIn: parent
                    text: "×"
                    color: Qt.rgba(0, 0, 0, 0.5)
                    font.family: errorWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.95
                    font.weight: Font.Bold
                    opacity: closeHover.hovered && errorWindow.active ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 120 } }
                }
                TapHandler { onTapped: errorWindow.close() }
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

        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: 24
            anchors.rightMargin: 24
            anchors.topMargin: 52
            anchors.bottomMargin: 20
            spacing: 12

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: errorWindow.action === "uninstall"
                    ? "Uninstall failed"
                    : "Install failed"
                color: "#D85D63"
                font.family: errorWindow.fontFamily
                font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.4
                font.weight: Font.DemiBold
            }

            Text {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: "Below is the tail of the install log. "
                    + "Retry runs the same action again; Close dismisses."
                color: Kirigami.Theme.disabledTextColor
                font.family: errorWindow.fontFamily
                font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.9
            }

            // Log viewer. A plain Flickable + read-only TextEdit rather
            // than QQC2.TextArea: the Breeze QQC2 style mis-binds its
            // TextArea contentItem ("Unable to assign … to QQuickTextInput"
            // warning in qqc2-breeze-style). TextEdit is a pure QtQuick
            // type with no style hook, so it sidesteps that bug while
            // keeping the same look (dark panel, monospace, scrollable).
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 8
                color: Qt.rgba(0, 0, 0, errorWindow.isDarkTheme ? 0.25 : 0.05)
                border.width: 0.5
                border.color: errorWindow.isDarkTheme
                    ? Qt.rgba(1, 1, 1, 0.08)
                    : Qt.rgba(0, 0, 0, 0.08)

                Flickable {
                    id: logFlick
                    anchors.fill: parent
                    anchors.margins: 8
                    clip: true
                    contentWidth: logArea.contentWidth
                    contentHeight: logArea.contentHeight
                    boundsBehavior: Flickable.StopAtBounds

                    QQC2.ScrollBar.vertical: QQC2.ScrollBar {}
                    QQC2.ScrollBar.horizontal: QQC2.ScrollBar {}

                    TextEdit {
                        id: logArea
                        width: Math.max(logFlick.width, contentWidth)
                        text: errorWindow.logText
                        readOnly: true
                        selectByMouse: true
                        wrapMode: TextEdit.NoWrap
                        font.family: "monospace"
                        font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.85
                        color: Kirigami.Theme.textColor
                        // Keep the latest log lines in view as text streams in.
                        onTextChanged: {
                            cursorPosition = length;
                            logFlick.contentY = Math.max(0, contentHeight - logFlick.height);
                        }
                    }
                }
            }

            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: 8

                QQC2.Button {
                    text: "Close"
                    onClicked: errorWindow.close()
                }

                QQC2.Button {
                    text: "Retry"
                    onClicked: {
                        retryRequested(errorWindow.action);
                        errorWindow.close();
                    }
                }
            }
        }
    }
}
