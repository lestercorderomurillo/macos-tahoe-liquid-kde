/*
    About This Computer — unified glass window.

    Hardware/OS data is gathered by ``mac-tahoe-about-info`` (Python,
    installed to ``~/.local/bin``). The helper consults every public
    source the user can read — DMI sysfs, /proc, lscpu, lspci, lsblk,
    glxinfo, free, dmidecode — picks the first non-empty answer per
    field, and emits JSON. This QML just renders it.

    Why a separate helper instead of inline shell-outs:
    - Locale: lscpu / lspci translate their labels when LANG != C, which
      silently broke every regex in the v0.13.x window (issue: "only RAM
      is shown"). The helper forces LC_ALL=C internally.
    - Fallbacks: each field has 2-4 sources; cascading them inline would
      need that many separate DataSource connections.
    - Tests: parsing logic is pytest-covered with captured fixtures from
      several distros. The QML side has nothing to test.

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

    // Whether to render in the active Plasma system font or in the
    // SF Pro fallback. Passed in from main.qml (which reads it from
    // ``Plasmoid.configuration.useSystemFont``). Kept as a plain
    // property so this file has no hard dependency on the Plasmoid
    // context and can be loaded standalone by tools/screenshots.
    property bool useSystemFont: true
    readonly property string fontFamily: useSystemFont ? Kirigami.Theme.defaultFont.family : "SF Pro Text"
    readonly property string fontFamilyDisplay: useSystemFont ? Kirigami.Theme.defaultFont.family : "SF Pro Display"

    // Override of the helper command, used by the screenshot harness
    // to point at a mock-data emitter. Defaults to the installed binary.
    property string fetcherCommand:
        "sh -c 'PATH=\"$HOME/.local/bin:$PATH\" mac-tahoe-about-info'"

    title: "About This Computer"
    width: 360
    height: 700
    minimumWidth: 360
    minimumHeight: 700
    maximumWidth: 360
    maximumHeight: 700
    flags: Qt.Window | Qt.FramelessWindowHint
    color: "transparent"

    readonly property bool isDarkTheme: {
        let bg = Kirigami.Theme.backgroundColor;
        return (bg.r * 0.299 + bg.g * 0.587 + bg.b * 0.114) < 0.5;
    }

    // Reference for two-line cell height. Cells whose content commonly
    // wraps to a second line (Chip, Graphics, Startup disk, OS) bind
    // their Layout.minimumHeight to ``2 * _fm.height`` so the row
    // pre-reserves two lines of vertical space. Without this, an empty
    // Text starts at 0 implicit height and the row visibly grows when
    // the wrapped value lands.
    FontMetrics {
        id: _fm
        font.family: aboutWindow.fontFamily
        font.pointSize: Kirigami.Theme.defaultFont.pointSize
    }

    // ── fetched values ───────────────────────────────────────────────────
    // The window opens before mac-tahoe-about-info finishes (~0.8s on a
    // fast machine, longer if dmidecode/glxinfo hit their timeouts). We
    // don't render placeholder dots — the rows below are bound to
    // ``infoReady`` and fade in once the helper returns. That keeps the
    // first paint silent instead of flashing "..." for a beat.
    //
    // Each default is a non-breaking space (NOT the empty string). The
    // grid still computes each row at one line of text height during
    // the loading phase, so when the real values land they swap in-place
    // with zero layout shift. Empty strings would collapse those Text
    // elements to 0 height and the whole grid would visibly grow.
    property bool infoReady: false
    readonly property string _placeholder: " "  // NBSP — reserves line height
    property string vendorDisplay: _placeholder
    property string modelDisplay: _placeholder
    property string yearDisplay: ""
    property string chipDisplay: _placeholder
    property string coresDisplay: _placeholder
    property string memoryDisplay: _placeholder
    property string graphicsDisplay: _placeholder
    property string diskDisplay: _placeholder
    property string networkDisplay: _placeholder
    property string serialDisplay: _placeholder
    property string osDisplay: _placeholder

    // ── data fetcher ─────────────────────────────────────────────────────
    // Single command, single JSON parse. The helper is installed to
    // ~/.local/bin which is already on PATH for the plasmashell session.
    P5Support.DataSource {
        id: infoSource
        engine: "executable"
        connectedSources: []

        onNewData: (sourceName, data) => {
            disconnectSource(sourceName);
            const stdout = (data["stdout"] || "").trim();
            if (!stdout) {
                console.warn("[AboutWindow] mac-tahoe-about-info returned no output");
                return;
            }
            let info;
            try {
                info = JSON.parse(stdout);
            } catch (e) {
                console.warn("[AboutWindow] failed to parse helper output:", e);
                return;
            }
            aboutWindow.vendorDisplay = info.vendor || "Personal Computer";
            aboutWindow.modelDisplay = info.model || "";
            aboutWindow.yearDisplay = info.year || "";
            aboutWindow.chipDisplay = info.chip || "Unknown";
            aboutWindow.coresDisplay = info.cores || "Unknown";
            aboutWindow.memoryDisplay = info.memory || "Unknown";
            aboutWindow.graphicsDisplay = info.graphics || "Unknown";
            aboutWindow.diskDisplay = info.disk || "Unknown";
            aboutWindow.networkDisplay = info.network || "Unknown";
            aboutWindow.serialDisplay = info.serial || "Not Available";
            aboutWindow.osDisplay = info.os || "Unknown";
            aboutWindow.infoReady = true;
        }

        function refresh() {
            // Force ~/.local/bin onto PATH: plasmashell inherits PATH
            // from whichever process started the session (kstart6 /
            // SDDM / systemd --user), and on some setups that runs
            // before .profile is sourced, so an unqualified
            // ``mac-tahoe-about-info`` would miss our install location.
            // The exact command is overridable via ``fetcherCommand``
            // so the screenshot harness can substitute a mock emitter.
            connectSource(aboutWindow.fetcherCommand);
        }
    }

    P5Support.DataSource {
        id: launcher
        engine: "executable"
        connectedSources: []
        onNewData: (src, _data) => { disconnectSource(src) }
        function exec(cmd: string): void { connectSource(cmd) }
    }

    // ── clipboard ────────────────────────────────────────────────────────
    // QtQuick has no clipboard API of its own, but TextEdit.copy() puts the
    // selected text on the system clipboard with no external process and no
    // polling (same trick as the installer's InstallError log viewer). We
    // keep one off-screen, build the report into it on demand, select all,
    // and copy. Plain QtQuick TextEdit — not a styled QQC2 control — so it
    // never warns about a missing Breeze background.
    TextEdit {
        id: clipboardProxy
        visible: false
        width: 0; height: 0
    }

    // Assemble the same field set the grid renders, "Label: Value" per line,
    // and place it on the clipboard. No-op until the helper has returned.
    function copyDetails(): void {
        if (!aboutWindow.infoReady)
            return;
        let header = aboutWindow.vendorDisplay;
        let sub = [];
        if (aboutWindow.modelDisplay && aboutWindow.modelDisplay.trim())
            sub.push(aboutWindow.modelDisplay);
        if (aboutWindow.yearDisplay)
            sub.push(aboutWindow.yearDisplay);
        if (sub.length)
            header += " (" + sub.join(", ") + ")";

        const rows = [
            ["Chip", aboutWindow.chipDisplay],
            ["Cores", aboutWindow.coresDisplay],
            ["Memory", aboutWindow.memoryDisplay],
            ["Graphics", aboutWindow.graphicsDisplay],
            ["Startup disk", aboutWindow.diskDisplay],
            ["Network", aboutWindow.networkDisplay],
            ["Serial number", aboutWindow.serialDisplay],
            ["OS", aboutWindow.osDisplay],
        ];
        let lines = [header, ""];
        for (const [label, value] of rows)
            lines.push(label + ": " + (value || "").trim());

        clipboardProxy.text = lines.join("\n");
        clipboardProxy.selectAll();
        clipboardProxy.copy();
        clipboardProxy.deselect();
    }

    // Pre-warm the data the moment the applet loads, while the window
    // is still hidden. main.qml instantiates AboutWindow at startup so
    // ``Component.onCompleted`` fires once per plasmashell session —
    // ~0.8s later the helper returns and ``infoReady`` flips silently.
    // By the time the user clicks "About This Computer" the values are
    // already in place and the window opens instantly, no fade-in.
    //
    // Reactivity to device changes: ``onVisibleChanged`` re-fetches on
    // every open, so any USB drive / VPN / display change since the
    // last open is reflected the next time the user opens the window.
    // We deliberately do NOT poll on a Timer — Plasma applets must not
    // spawn subprocesses on a recurring schedule (saved rule).
    Component.onCompleted: infoSource.refresh()

    onVisibleChanged: {
        if (visible)
            infoSource.refresh();
    }

    // unified glass frame
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

        // drag from anywhere
        MouseArea {
            anchors.fill: parent
            property point clickPos: Qt.point(0, 0)
            onPressed: (mouse) => { clickPos = Qt.point(mouse.x, mouse.y) }
            onPositionChanged: (mouse) => {
                aboutWindow.x += mouse.x - clickPos.x;
                aboutWindow.y += mouse.y - clickPos.y;
            }
        }

        // window buttons
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
                    text: "×"; color: Qt.rgba(0, 0, 0, 0.5)
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

        // content
        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            Item { Layout.preferredHeight: 70 }

            Kirigami.Icon {
                Layout.alignment: Qt.AlignHCenter
                implicitWidth: 132; implicitHeight: 132
                source: "computer"
            }

            Item { Layout.preferredHeight: 18 }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: aboutWindow.vendorDisplay
                color: Kirigami.Theme.textColor
                font.family: aboutWindow.fontFamilyDisplay
                font.pixelSize: 22
                font.bold: true
                opacity: aboutWindow.infoReady ? 1.0 : 0.0
                Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutQuad } }
            }

            Item { Layout.preferredHeight: 4 }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: {
                    let parts = [];
                    if (aboutWindow.modelDisplay && aboutWindow.modelDisplay.trim())
                        parts.push(aboutWindow.modelDisplay);
                    if (aboutWindow.yearDisplay)
                        parts.push(aboutWindow.yearDisplay);
                    // Always render at least a NBSP so this row reserves
                    // one line of vertical space even on machines where
                    // DMI returned no model — avoids the layout shift
                    // when the real value (or empty model) lands.
                    return parts.length ? parts.join(", ") : " ";
                }
                color: Kirigami.Theme.disabledTextColor
                font.family: aboutWindow.fontFamily
                font.pixelSize: 13
                opacity: aboutWindow.infoReady ? 1.0 : 0.0
                Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutQuad } }
            }

            Item { Layout.preferredHeight: 36 }

            GridLayout {
                Layout.alignment: Qt.AlignHCenter
                columns: 2
                columnSpacing: 16
                rowSpacing: 6
                // Whole table fades in together once the helper returns —
                // no per-row pop-in, no placeholder dots.
                opacity: aboutWindow.infoReady ? 1.0 : 0.0
                Behavior on opacity { NumberAnimation { duration: 260; easing.type: Easing.OutQuad } }

                // Chip
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
                    text: aboutWindow.chipDisplay
                    color: Kirigami.Theme.textColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.preferredWidth: 180
                    Layout.minimumHeight: 2 * _fm.height
                    wrapMode: Text.WordWrap
                    verticalAlignment: Text.AlignVCenter
                }

                // Cores
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
                    text: aboutWindow.coresDisplay
                    color: Kirigami.Theme.textColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.preferredWidth: 180
                }

                // Memory
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
                    text: aboutWindow.memoryDisplay
                    color: Kirigami.Theme.textColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.preferredWidth: 180
                }

                // Graphics
                Text {
                    text: "Graphics"
                    color: Kirigami.Theme.disabledTextColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.alignment: Qt.AlignRight
                    Layout.preferredWidth: 110
                    horizontalAlignment: Text.AlignRight
                }
                Text {
                    text: aboutWindow.graphicsDisplay
                    color: Kirigami.Theme.textColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.preferredWidth: 180
                    Layout.minimumHeight: 2 * _fm.height
                    wrapMode: Text.WordWrap
                    verticalAlignment: Text.AlignVCenter
                }

                // Startup disk
                Text {
                    text: "Startup disk"
                    color: Kirigami.Theme.disabledTextColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.alignment: Qt.AlignRight
                    Layout.preferredWidth: 110
                    horizontalAlignment: Text.AlignRight
                }
                Text {
                    text: aboutWindow.diskDisplay
                    color: Kirigami.Theme.textColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.preferredWidth: 180
                    Layout.minimumHeight: 2 * _fm.height
                    wrapMode: Text.WordWrap
                    verticalAlignment: Text.AlignVCenter
                }

                // Network address
                Text {
                    text: "Network"
                    color: Kirigami.Theme.disabledTextColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.alignment: Qt.AlignRight
                    Layout.preferredWidth: 110
                    horizontalAlignment: Text.AlignRight
                }
                Text {
                    text: aboutWindow.networkDisplay
                    color: Kirigami.Theme.textColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.preferredWidth: 180
                    elide: Text.ElideRight
                }

                // Serial number
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
                    text: aboutWindow.serialDisplay
                    color: Kirigami.Theme.textColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.preferredWidth: 180
                    elide: Text.ElideRight
                }

                // OS
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
                    text: aboutWindow.osDisplay
                    color: Kirigami.Theme.textColor
                    font.family: aboutWindow.fontFamily
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                    Layout.preferredWidth: 180
                    Layout.minimumHeight: 2 * _fm.height
                    wrapMode: Text.WordWrap
                    verticalAlignment: Text.AlignVCenter
                }
            }

            Item { Layout.preferredHeight: 22 }

            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: 8

                QQC2.Button {
                    text: "More Info..."
                    onClicked: {
                        launcher.exec("kinfocenter");
                        aboutWindow.close();
                    }
                }

                QQC2.Button {
                    text: "Report a Bug..."
                    onClicked: {
                        launcher.exec("xdg-open https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new");
                        aboutWindow.close();
                    }
                }

                // Copy all the gathered details to the clipboard. Identical to
                // the two text buttons above — a plain QQC2.Button with NO
                // custom background or contentItem — so it inherits the exact
                // same Breeze rounding, fill, hover/pressed, and click handling.
                // The only difference is it shows an icon instead of text. The
                // bundled Lucide "copy" SVG is monochrome, so the native style
                // tints it to the button text colour automatically; on a copy
                // it flips to the theme checkmark for ~1.5s for confirmation.
                QQC2.Button {
                    id: copyButton
                    property bool justCopied: false
                    enabled: aboutWindow.infoReady
                    display: QQC2.AbstractButton.IconOnly
                    icon.name: justCopied ? "dialog-ok" : ""
                    icon.source: justCopied ? "" : Qt.resolvedUrl("copy.svg")
                    QQC2.ToolTip.text: justCopied ? "Copied" : "Copy details"
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.delay: 400
                    onClicked: {
                        aboutWindow.copyDetails();
                        justCopied = true;
                        copiedReset.restart();
                    }

                    Timer {
                        id: copiedReset
                        interval: 1500
                        onTriggered: copyButton.justCopied = false
                    }
                }
            }

            Item { Layout.fillHeight: true }
        }
    }
}
