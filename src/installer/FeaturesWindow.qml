/*
    Features picker — a glass companion window for InstallerWindow.

    Reads the current feature state by shelling out to
    ``installer_ui.py --dump-features`` (which already knows where
    ``features.json`` lives), renders one toggle per entry, and saves
    back via ``installer_ui.py --save-features '<json>'``.

    The Python side is the single source of truth for the feature list
    and persistence path — this file just renders what it gets.

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtQuick.Window

import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5Support

Window {
    id: featuresWindow

    property string launcherScriptPath: ""
    property var items: []
    property bool loaded: false
    property string statusMessage: ""
    property string statusKind: "idle"

    readonly property string fontFamily: Kirigami.Theme.defaultFont.family
    readonly property bool isDarkTheme: {
        const bg = Kirigami.Theme.backgroundColor;
        return (bg.r * 0.299 + bg.g * 0.587 + bg.b * 0.114) < 0.5;
    }

    title: "Features"
    width: 880
    height: 640
    minimumWidth: 880
    minimumHeight: 640
    maximumWidth: 880
    maximumHeight: 640
    flags: Qt.Window | Qt.FramelessWindowHint
    color: "transparent"

    Component.onCompleted: {
        const s = Screen;
        x = Math.round((s.width - width) / 2);
        y = Math.round((s.height - height) / 2);
    }

    function _shellQuote(text: string): string {
        return "'" + text.replace(/'/g, "'\"'\"'") + "'";
    }

    function refresh(): void {
        const cmd = "python3 " + _shellQuote(launcherScriptPath) + " --dump-features";
        loader.connectSource(cmd + " # dump " + Date.now());
    }

    function save(): void {
        const payload = {};
        for (let i = 0; i < items.length; ++i)
            payload[items[i].key] = items[i].enabled;
        const json = JSON.stringify(payload);
        const cmd = "python3 " + _shellQuote(launcherScriptPath)
                  + " --save-features " + _shellQuote(json);
        saver.connectSource(cmd + " # save " + Date.now());
    }

    P5Support.DataSource {
        id: loader
        engine: "executable"
        connectedSources: []
        onNewData: (sourceName, data) => {
            disconnectSource(sourceName);
            const stdout = (data["stdout"] || "").trim();
            if (!stdout) return;
            try {
                const parsed = JSON.parse(stdout);
                featuresWindow.items = parsed.items || [];
                featuresWindow.loaded = true;
            } catch (e) {
                featuresWindow.statusKind = "error";
                featuresWindow.statusMessage = "Could not load features.";
            }
        }
    }

    P5Support.DataSource {
        id: saver
        engine: "executable"
        connectedSources: []
        onNewData: (sourceName, data) => {
            disconnectSource(sourceName);
        }
    }

    onVisibleChanged: {
        if (visible) refresh();
    }

    Rectangle {
        id: glass
        anchors.fill: parent
        radius: 22
        color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                       Kirigami.Theme.backgroundColor.g,
                       Kirigami.Theme.backgroundColor.b, 0.82)
        border.width: 0.5
        border.color: featuresWindow.isDarkTheme
            ? Qt.rgba(1, 1, 1, 0.12)
            : Qt.rgba(0, 0, 0, 0.10)
        layer.enabled: true

        MouseArea {
            anchors.fill: parent
            property point clickPos: Qt.point(0, 0)
            onPressed: (mouse) => { clickPos = Qt.point(mouse.x, mouse.y) }
            onPositionChanged: (mouse) => {
                featuresWindow.x += mouse.x - clickPos.x;
                featuresWindow.y += mouse.y - clickPos.y;
            }
        }

        Row {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.leftMargin: 14
            anchors.topMargin: 14
            spacing: 8
            z: 1

            readonly property color inactiveColor: featuresWindow.isDarkTheme
                ? Qt.rgba(1, 1, 1, 0.2) : Qt.rgba(0, 0, 0, 0.12)
            readonly property color inactiveBorder: featuresWindow.isDarkTheme
                ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.06)

            Rectangle {
                width: 14
                height: 14
                radius: 7
                color: featuresWindow.active ? "#FF5F57" : parent.inactiveColor
                border.width: 0.5
                border.color: featuresWindow.active
                    ? Qt.rgba(0, 0, 0, 0.12)
                    : parent.inactiveBorder

                HoverHandler { id: closeHover }
                Text {
                    anchors.centerIn: parent
                    text: "×"
                    color: Qt.rgba(0, 0, 0, 0.5)
                    font.family: featuresWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.95
                    font.weight: Font.Bold
                    opacity: closeHover.hovered && featuresWindow.active ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 120 } }
                }
                TapHandler { onTapped: featuresWindow.close() }
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
            anchors.topMargin: 48
            anchors.bottomMargin: 20
            spacing: 0

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "Features"
                color: Kirigami.Theme.textColor
                font.family: featuresWindow.fontFamily
                font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.4
                font.weight: Font.DemiBold
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 420
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: "Choose what gets installed"
                color: Kirigami.Theme.disabledTextColor
                font.family: featuresWindow.fontFamily
                font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.9
            }

            Item { Layout.preferredHeight: 18 }

            GridLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.leftMargin: 48
                Layout.rightMargin: 48
                columns: 2
                columnSpacing: 16
                rowSpacing: 8
                flow: GridLayout.TopToBottom
                rows: Math.ceil(featuresWindow.items.length / 2)

                Repeater {
                    model: featuresWindow.items
                    delegate: RowLayout {
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1   // forces equal column split
                        spacing: 0

                        // Centre the text+switch group in the column.
                        Item { Layout.fillWidth: true }

                        ColumnLayout {
                            // Natural content width (capped so long
                            // descriptions wrap) so the switch hugs the text.
                            Layout.maximumWidth: 170
                            spacing: 1

                            Text {
                                Layout.fillWidth: true
                                text: modelData.label
                                color: Kirigami.Theme.textColor
                                font.family: featuresWindow.fontFamily
                                font.pointSize: Kirigami.Theme.defaultFont.pointSize
                                font.weight: Font.Medium
                                elide: Text.ElideRight
                            }

                            Text {
                                Layout.fillWidth: true
                                text: modelData.description
                                color: Kirigami.Theme.disabledTextColor
                                font.family: featuresWindow.fontFamily
                                font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.82
                                wrapMode: Text.WordWrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                            }
                        }

                        // Fixed gap between the text block and the switch.
                        Item { Layout.preferredWidth: 22 }

                        QQC2.Switch {
                            id: featureSwitch
                            Layout.alignment: Qt.AlignVCenter
                            checked: modelData.enabled
                            onToggled: {
                                const items = featuresWindow.items.slice();
                                items[index] = Object.assign({}, items[index],
                                                             {enabled: checked});
                                featuresWindow.items = items;
                                featuresWindow.save();
                            }

                            // macOS-style filled switch: blue track on,
                            // grey off, white knob, no border.
                            indicator: Rectangle {
                                implicitWidth: 38
                                implicitHeight: 22
                                radius: height / 2
                                color: featureSwitch.checked
                                    ? "#0A84FF"
                                    : (featuresWindow.isDarkTheme ? "#5A5A5E" : "#D8D8DC")
                                border.width: 0

                                Behavior on color {
                                    ColorAnimation { duration: 120 }
                                }

                                Rectangle {
                                    width: 18
                                    height: 18
                                    radius: height / 2
                                    y: (parent.height - height) / 2
                                    x: featureSwitch.checked
                                        ? parent.width - width - 2
                                        : 2
                                    color: "white"

                                    Behavior on x {
                                        NumberAnimation {
                                            duration: 120
                                            easing.type: Easing.OutQuad
                                        }
                                    }
                                }
                            }
                        }

                        Item { Layout.fillWidth: true }
                    }
                }
            }

            Item { Layout.preferredHeight: 12 }

            Text {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 420
                visible: statusMessage.length > 0
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: featuresWindow.statusMessage
                color: featuresWindow.statusKind === "error"
                    ? "#D85D63"
                    : Kirigami.Theme.disabledTextColor
                font.family: featuresWindow.fontFamily
                font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.9
            }
        }
    }
}
