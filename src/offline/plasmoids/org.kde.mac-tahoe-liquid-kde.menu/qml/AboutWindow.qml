/*
    About This Computer — unified glass window.

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtQuick.Window

import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid
import org.kde.plasma.plasma5support as P5Support

Window {
    id: aboutWindow

    readonly property bool useSystemFont: Plasmoid.configuration.useSystemFont
    readonly property string fontFamily: useSystemFont ? Kirigami.Theme.defaultFont.family : "SF Pro Text"
    readonly property string fontFamilyDisplay: useSystemFont ? Kirigami.Theme.defaultFont.family : "SF Pro Display"

    title: "About This Computer"
    width: 340
    height: 580
    minimumWidth: 340
    minimumHeight: 580
    maximumWidth: 340
    maximumHeight: 580
    flags: Qt.Window | Qt.FramelessWindowHint
    color: "transparent"

    readonly property bool isDarkTheme: {
        let bg = Kirigami.Theme.backgroundColor;
        return (bg.r * 0.299 + bg.g * 0.587 + bg.b * 0.114) < 0.5;
    }

    property string deviceName: ""
    property string boardVendor: ""
    property string boardName: ""
    property string boardYear: ""
    property string memoryInfo: ""
    property string cpuInfo: ""
    property string cpuCores: ""
    property string serialNumber: ""
    property string osPrettyName: ""

    // ── system info fetcher ────────────────────────────────────────
    P5Support.DataSource {
        id: infoSource
        engine: "executable"
        connectedSources: []

        onNewData: (sourceName, data) => {
            let stdout = data["stdout"] || "";

            if (sourceName.indexOf("product_name") !== -1) {
                let name = stdout.trim();
                if (name && name !== "" && name !== "System Product Name"
                    && name !== "To Be Filled By O.E.M." && name !== "Default string")
                    aboutWindow.deviceName = name;
            } else if (sourceName.indexOf("hostname") !== -1) {
                if (!aboutWindow.deviceName)
                    aboutWindow.deviceName = stdout.trim() || "Computer";
            } else if (sourceName.indexOf("meminfo") !== -1) {
                let match = stdout.match(/MemTotal:\s+(\d+)/);
                if (match) {
                    let kB = parseInt(match[1]);
                    let gB = kB / 1048576;
                    let sizes = [1, 2, 4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 256, 512];
                    let best = sizes[0];
                    for (let i = 0; i < sizes.length; i++) {
                        if (Math.abs(sizes[i] - gB) < Math.abs(best - gB))
                            best = sizes[i];
                    }
                    aboutWindow.memoryInfo = best + " GB";
                }
            } else if (sourceName.indexOf("lscpu") !== -1) {
                let match = stdout.match(/Model name:\s+(.+)/);
                if (match) {
                    // Clean up: remove excess like "(R)", "(TM)", "CPU @", "with Radeon..."
                    let raw = match[1].trim();
                    raw = raw.replace(/\(R\)|\(TM\)/gi, "");
                    raw = raw.replace(/\s+CPU\s*/i, " ");
                    raw = raw.replace(/\s*@\s*[\d.]+\s*GHz/i, "");
                    raw = raw.replace(/\s+with\s+.*/i, "");
                    raw = raw.replace(/\s+\d+-Core.*/i, "");
                    raw = raw.replace(/\s+/g, " ").trim();
                    aboutWindow.cpuInfo = raw;
                }
                let cores = stdout.match(/^CPU\(s\):\s+(\d+)/m);
                if (cores)
                    aboutWindow.cpuCores = cores[1];
            } else if (sourceName.indexOf("board_serial") !== -1) {
                let s = stdout.trim();
                aboutWindow.serialNumber = (s && s !== "" && s !== "None"
                    && s !== "Default string" && s !== "To Be Filled By O.E.M.")
                    ? s : "Not Available";
            } else if (sourceName.indexOf("board_vendor") !== -1) {
                let v = stdout.trim();
                if (v && v !== "" && v !== "Default string"
                    && v !== "To Be Filled By O.E.M.") {
                    // Shorten known vendor names
                    let shorts = {
                        "ASUSTeK COMPUTER INC.": "ASUS",
                        "Micro-Star International Co., Ltd.": "MSI",
                        "LENOVO": "Lenovo",
                        "Hewlett-Packard": "HP",
                        "Dell Inc.": "Dell",
                        "Gigabyte Technology Co., Ltd.": "Gigabyte",
                        "ASRock": "ASRock",
                        "Apple Inc.": "Apple"
                    };
                    aboutWindow.boardVendor = shorts[v] || v.replace(/\s*(Inc\.?|Co\.?,?\s*Ltd\.?|COMPUTER|Corporation|Corp\.?)$/gi, "").trim();
                }
            } else if (sourceName.indexOf("board_name") !== -1) {
                let name = stdout.trim();
                if (name && name !== "" && name !== "Default string"
                    && name !== "To Be Filled By O.E.M.")
                    aboutWindow.boardName = name;
            } else if (sourceName.indexOf("bios_date") !== -1) {
                let match = stdout.trim().match(/(\d{4})/);
                if (match)
                    aboutWindow.boardYear = match[1];
            } else if (sourceName.indexOf("os-release") !== -1) {
                let match = stdout.match(/^PRETTY_NAME="?([^"\n]+)"?/m);
                if (match)
                    aboutWindow.osPrettyName = match[1].trim();
            }

            disconnectSource(sourceName);
        }

        function exec(cmd: string): void {
            connectSource(cmd);
        }
    }

    P5Support.DataSource {
        id: launcher
        engine: "executable"
        connectedSources: []
        onNewData: (src, _data) => { disconnectSource(src) }
        function exec(cmd: string): void { connectSource(cmd) }
    }

    onVisibleChanged: {
        if (visible) {
            infoSource.exec("cat /sys/devices/virtual/dmi/id/product_name");
            infoSource.exec("hostname");
            infoSource.exec("cat /proc/meminfo");
            infoSource.exec("lscpu");
            infoSource.exec("cat /sys/devices/virtual/dmi/id/board_serial");
            infoSource.exec("cat /sys/devices/virtual/dmi/id/board_vendor");
            infoSource.exec("cat /sys/devices/virtual/dmi/id/board_name");
            infoSource.exec("cat /sys/devices/virtual/dmi/id/bios_date");
            infoSource.exec("cat /etc/os-release");
        }
    }

    // ── unified glass frame ────────────────────────────────────────
    Rectangle {
        id: glass
        anchors.fill: parent
        radius: 22
        color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                       Kirigami.Theme.backgroundColor.g,
                       Kirigami.Theme.backgroundColor.b, 0.82)
        border.width: 0.5
        border.color: aboutWindow.isDarkTheme
                      ? Qt.rgba(1, 1, 1, 0.12)
                      : Qt.rgba(0, 0, 0, 0.10)

        layer.enabled: true

        // ── drag from anywhere ─────────────────────────────────────
        MouseArea {
            anchors.fill: parent
            property point clickPos: Qt.point(0, 0)
            onPressed: (mouse) => { clickPos = Qt.point(mouse.x, mouse.y) }
            onPositionChanged: (mouse) => {
                aboutWindow.x += mouse.x - clickPos.x;
                aboutWindow.y += mouse.y - clickPos.y;
            }
        }

        // ── window buttons ─────────────────────────────────────────
        Row {
            anchors { left: parent.left; top: parent.top; leftMargin: 14; topMargin: 14 }
            spacing: 8
            z: 1

            readonly property color inactiveColor: aboutWindow.isDarkTheme
                ? Qt.rgba(1, 1, 1, 0.2) : Qt.rgba(0, 0, 0, 0.12)
            readonly property color inactiveBorder: aboutWindow.isDarkTheme
                ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.06)

            // Close
            Rectangle {
                width: 14; height: 14; radius: 7
                color: aboutWindow.active ? "#FF5F57" : parent.inactiveColor
                border.width: 0.5
                border.color: aboutWindow.active ? Qt.rgba(0, 0, 0, 0.12) : parent.inactiveBorder
                Behavior on color { ColorAnimation { duration: 150 } }

                HoverHandler { id: closeHover }
                Text {
                    anchors.centerIn: parent
                    text: "\u00d7"; color: Qt.rgba(0, 0, 0, 0.5)
                    font.pixelSize: 11; font.bold: true
                    opacity: closeHover.hovered && aboutWindow.active ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 120 } }
                }
                TapHandler { onTapped: aboutWindow.close() }
            }

            // Minimize (decorative)
            Rectangle {
                width: 14; height: 14; radius: 7
                color: parent.inactiveColor
                border.width: 0.5
                border.color: parent.inactiveBorder
            }

            // Maximize (decorative)
            Rectangle {
                width: 14; height: 14; radius: 7
                color: parent.inactiveColor
                border.width: 0.5
                border.color: parent.inactiveBorder
            }
        }

        // ── content ────────────────────────────────────────────────
        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            Item { Layout.preferredHeight: 78 }

            Kirigami.Icon {
                Layout.alignment: Qt.AlignHCenter
                implicitWidth: 140; implicitHeight: 140
                source: "computer"
            }

            Item { Layout.preferredHeight: 20 }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: aboutWindow.boardVendor || "Personal Computer"
                color: Kirigami.Theme.textColor
                font.family: aboutWindow.fontFamilyDisplay
                font.pixelSize: 22
                font.bold: true
            }

            Item { Layout.preferredHeight: 4 }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: {
                    let parts = [];
                    if (aboutWindow.boardName) parts.push(aboutWindow.boardName);
                    if (aboutWindow.boardYear) parts.push(aboutWindow.boardYear);
                    return parts.join(", ");
                }
                color: Kirigami.Theme.disabledTextColor
                font.family: aboutWindow.fontFamily
                font.pixelSize: 13
                visible: text !== ""
            }

            Item { Layout.preferredHeight: 48 }

            GridLayout {
                Layout.alignment: Qt.AlignHCenter
                columns: 2
                columnSpacing: 16
                rowSpacing: 6

                Text {
                    text: "Chip"
                    color: Kirigami.Theme.disabledTextColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.alignment: Qt.AlignRight
                    Layout.preferredWidth: 110
                    horizontalAlignment: Text.AlignRight
                }
                Text {
                    text: aboutWindow.cpuInfo || "..."
                    color: Kirigami.Theme.textColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.preferredWidth: 150
                }

                Text {
                    text: "Cores"
                    color: Kirigami.Theme.disabledTextColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.alignment: Qt.AlignRight
                    Layout.preferredWidth: 110
                    horizontalAlignment: Text.AlignRight
                }
                Text {
                    text: aboutWindow.cpuCores || "..."
                    color: Kirigami.Theme.textColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.preferredWidth: 150
                }

                Text {
                    text: "Memory"
                    color: Kirigami.Theme.disabledTextColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.alignment: Qt.AlignRight
                    Layout.preferredWidth: 110
                    horizontalAlignment: Text.AlignRight
                }
                Text {
                    text: aboutWindow.memoryInfo || "..."
                    color: Kirigami.Theme.textColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.preferredWidth: 150
                }

                Text {
                    text: "Serial number"
                    color: Kirigami.Theme.disabledTextColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.alignment: Qt.AlignRight
                    Layout.preferredWidth: 110
                    horizontalAlignment: Text.AlignRight
                }
                Text {
                    text: aboutWindow.serialNumber || "..."
                    color: Kirigami.Theme.textColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.preferredWidth: 150
                }

                Text {
                    text: "OS"
                    color: Kirigami.Theme.disabledTextColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.alignment: Qt.AlignRight
                    Layout.preferredWidth: 110
                    horizontalAlignment: Text.AlignRight
                }
                Text {
                    text: aboutWindow.osPrettyName || "..."
                    color: Kirigami.Theme.textColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.preferredWidth: 150
                }
            }

            Item { Layout.preferredHeight: 36 }

            QQC2.Button {
                Layout.alignment: Qt.AlignHCenter
                text: "More Info..."
                onClicked: {
                    launcher.exec("kinfocenter");
                    aboutWindow.close();
                }
            }

            Item { Layout.fillHeight: true }
        }
    }
}
