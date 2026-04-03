/*
    About This Computer — macOS-style system info window.

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
    id: aboutWindow

    title: "About This Computer"
    width: 340
    height: 580
    minimumWidth: 340
    minimumHeight: 580
    maximumWidth: 340
    maximumHeight: 580
    flags: Qt.Dialog

    property string deviceName: ""
    property string boardName: ""
    property string boardYear: ""
    property string memoryInfo: ""
    property string cpuInfo: ""
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
                if (match)
                    aboutWindow.cpuInfo = match[1].trim();
            } else if (sourceName.indexOf("board_serial") !== -1) {
                let s = stdout.trim();
                aboutWindow.serialNumber = (s && s !== "" && s !== "None"
                    && s !== "Default string" && s !== "To Be Filled By O.E.M.")
                    ? s : "Not Available";
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
            infoSource.exec("cat /sys/devices/virtual/dmi/id/board_name");
            infoSource.exec("cat /sys/devices/virtual/dmi/id/bios_date");
            infoSource.exec("cat /etc/os-release");
        }
    }

    color: "transparent"

    // ── content ────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                       Kirigami.Theme.backgroundColor.g,
                       Kirigami.Theme.backgroundColor.b, 0.75)

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            Item { Layout.preferredHeight: 32 }

            // ── computer icon ──────────────────────────────────────
            Kirigami.Icon {
                Layout.alignment: Qt.AlignHCenter
                implicitWidth: 140; implicitHeight: 140
                source: "computer-symbolic"
            }

            Item { Layout.preferredHeight: 20 }

            // ── device name ────────────────────────────────────────
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "Personal Computer"
                color: Kirigami.Theme.textColor
                font.pixelSize: 22
                font.bold: true
            }

            Item { Layout.preferredHeight: 4 }

            // ── motherboard + year subtitle ────────────────────────
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: {
                    let parts = [];
                    if (aboutWindow.boardName) parts.push(aboutWindow.boardName);
                    if (aboutWindow.boardYear) parts.push(aboutWindow.boardYear);
                    return parts.join(", ");
                }
                color: Kirigami.Theme.disabledTextColor
                font.pixelSize: 13
                visible: text !== ""
            }

            Item { Layout.preferredHeight: 48 }

            // ── specs grid ─────────────────────────────────────────
            GridLayout {
                Layout.alignment: Qt.AlignHCenter
                columns: 2
                columnSpacing: 16
                rowSpacing: 5

                Text {
                    text: "Chip"
                    color: Kirigami.Theme.disabledTextColor
                    font: Kirigami.Theme.defaultFont
                    Layout.alignment: Qt.AlignRight | Qt.AlignTop
                }
                Text {
                    text: aboutWindow.cpuInfo || "..."
                    color: Kirigami.Theme.textColor
                    font: Kirigami.Theme.defaultFont
                    Layout.maximumWidth: 180
                    wrapMode: Text.WordWrap
                }

                Text {
                    text: "Memory"
                    color: Kirigami.Theme.disabledTextColor
                    font: Kirigami.Theme.defaultFont
                    Layout.alignment: Qt.AlignRight
                }
                Text {
                    text: aboutWindow.memoryInfo || "..."
                    color: Kirigami.Theme.textColor
                    font: Kirigami.Theme.defaultFont
                }

                Text {
                    text: "Serial number"
                    color: Kirigami.Theme.disabledTextColor
                    font: Kirigami.Theme.defaultFont
                    Layout.alignment: Qt.AlignRight
                }
                Text {
                    text: aboutWindow.serialNumber || "..."
                    color: Kirigami.Theme.textColor
                    font: Kirigami.Theme.defaultFont
                }

                Text {
                    text: "OS"
                    color: Kirigami.Theme.disabledTextColor
                    font: Kirigami.Theme.defaultFont
                    Layout.alignment: Qt.AlignRight
                }
                Text {
                    text: aboutWindow.osPrettyName || "..."
                    color: Kirigami.Theme.textColor
                    font: Kirigami.Theme.defaultFont
                }
            }

            Item { Layout.preferredHeight: 36 }

            // ── more info button ───────────────────────────────────
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
