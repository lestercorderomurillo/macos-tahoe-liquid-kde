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

    // ── update banner state ──────────────────────────────────────────────
    // Populated by installer.checkForUpdates() → onUpdateChecked. The
    // banner stays hidden unless GitHub reports a strictly newer release,
    // mirroring the CLI's `./install --check-update` verdict. Network
    // failures (and the MAC_TAHOE_NO_UPDATE_CHECK opt-out) leave
    // updateAvailable false, so the banner simply never appears.
    property bool updateAvailable: false
    property string updateCurrent: ""
    property string updateLatest: ""
    property bool logoAnimating: true

    readonly property bool busy: viewMode === "installing"
    readonly property string fontFamily: Kirigami.Theme.defaultFont.family
    readonly property string launcherScriptPath: _localPath(Qt.resolvedUrl("installer_ui.py"))
    readonly property bool isDarkTheme: {
        const bg = Kirigami.Theme.backgroundColor;
        return (bg.r * 0.299 + bg.g * 0.587 + bg.b * 0.114) < 0.5;
    }

    title: "MacTahoe Liquid KDE Installer"
    width: 1000
    height: 684
    minimumWidth: 1000
    minimumHeight: 684
    maximumWidth: 1000
    maximumHeight: 684
    flags: Qt.Window | Qt.FramelessWindowHint
    color: "transparent"

    Component.onCompleted: {
        const s = Screen;
        x = Math.round((s.width - width) / 2);
        y = Math.round((s.height - height) / 2);
        // Fire the GitHub round-trip once, off the GUI thread. The verdict
        // lands later via onUpdateChecked; nothing blocks the first paint.
        if (installer)
            installer.checkForUpdates();
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
        function onUpdateChecked(status) {
            installerWindow.updateCurrent = status.current || "";
            installerWindow.updateLatest = status.latest || "";
            installerWindow.updateAvailable = status.available === true;
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

            // ── update banner ─────────────────────────────────────────────
            // A quiet macOS-style pill that fades in only when GitHub has a
            // strictly newer release. Same verdict and copy as the CLI's
            // `./install --check-update`. Clicking it copies the upgrade
            // command; the user still upgrades via git pull && ./install.
            Rectangle {
                id: updateBanner
                Layout.alignment: Qt.AlignHCenter
                Layout.bottomMargin: 14
                visible: installerWindow.updateAvailable
                implicitWidth: updateRow.implicitWidth + 32
                implicitHeight: 34
                radius: height / 2
                color: installerWindow.isDarkTheme
                    ? Qt.rgba(0.0, 0.48, 1.0, 0.18)
                    : Qt.rgba(0.0, 0.48, 1.0, 0.12)
                border.width: 1
                border.color: Qt.rgba(0.0, 0.48, 1.0, 0.35)

                Row {
                    id: updateRow
                    anchors.centerIn: parent
                    spacing: 8

                    Kirigami.Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 16
                        height: 16
                        source: "arrow-up"
                        color: "#007AFF"
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Update available: " + installerWindow.updateCurrent
                            + " → " + installerWindow.updateLatest
                            + "   ·   run git pull && ./install"
                        color: Kirigami.Theme.textColor
                        font.family: installerWindow.fontFamily
                        font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.95
                        font.weight: Font.DemiBold
                    }
                }

                HoverHandler {
                    cursorShape: Qt.PointingHandCursor
                    enabled: !installerWindow.busy
                }
                TapHandler {
                    enabled: !installerWindow.busy
                    onTapped: {
                        updateClipboard.text = "git pull && ./install";
                        updateClipboard.selectAll();
                        updateClipboard.copy();
                        updateClipboard.deselect();
                    }
                }

                // Off-screen TextEdit, used only as a clipboard via copy().
                TextEdit {
                    id: updateClipboard
                    visible: false
                    width: 0
                    height: 0
                }
            }

            // ── logo area (Canvas 2D stroke-dasharray → crossfade to PNG) ──
            // Qt's Image can't play SMIL animations, and ShapePath doesn't
            // have strokeDashArray in this Qt version. Canvas 2D with
            // setLineDash() gives the Apple drawing effect and stays fluid
            // because only the dash array changes each frame, not the path.
            Item {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 560
                Layout.preferredHeight: 252

                clip: true

                Canvas {
                    id: logoCanvas
                    anchors.fill: parent
                    antialiasing: true

                    // Uniform scale: the path is authored in a 320×180
                    // viewBox; scaling each axis to the 20:9 container
                    // stretched the lettering and made the round pen
                    // elliptical (lineWidth scales per-axis).
                    readonly property real svgScale: Math.min(width / 320, height / 180)
                    // actual path length computed numerically: ≈1395.7 viewBox units
                    readonly property real dashTotal: 1396
                    property real dashProgress: 0

                    opacity: installerWindow.logoAnimating ? 1 : 0
                    visible: opacity > 0

                    Behavior on opacity {
                        NumberAnimation { duration: 100; easing: Easing.OutCubic }
                    }

                    // InQuad → starts slow on each letter, picks up speed.
                    NumberAnimation on dashProgress {
                        id: logoDrawAnim
                        from: 0; to: 1
                        duration: 5000
                        easing.type: Easing.InQuad
                        running: installerWindow.viewMode === "main"
                                 && installerWindow.logoAnimating
                        onFinished: installerWindow.logoAnimating = false
                    }

                    onDashProgressChanged: requestPaint()

                    onPaint: {
                        var ctx = logoCanvas.getContext('2d');
                        if (!ctx) return;
                        ctx.clearRect(0, 0, width, height);
                        ctx.save();

                        // centre the path's bounding box (x 26.8–310.1,
                        // y 23.5–144.7 in viewBox units) in the canvas
                        ctx.translate(
                            width  / 2 - 168.45 * svgScale,
                            height / 2 - 84.1   * svgScale
                        );
                        ctx.scale(svgScale, svgScale);

                        ctx.strokeStyle = installerWindow.isDarkTheme
                            ? 'rgba(255,255,255,0.85)'
                            : 'rgba(0,0,0,0.70)';
                        ctx.lineWidth = 2.5;
                        ctx.lineCap = 'round';
                        ctx.lineJoin = 'round';

                        var drawn = dashProgress * dashTotal;
                        ctx.setLineDash([drawn, dashTotal - drawn]);

                        // 14 hardcoded bezier commands from the original SVG path,
                        // all in absolute viewBox coords (avoids JS parser bugs).
                        ctx.beginPath();
                        ctx.moveTo(26.816767,36.748271);
                        ctx.bezierCurveTo(43.203424,67.240957,66.474145,0.318121,55.270041,32.476855);
                        ctx.bezierCurveTo(32.265545,98.505836,29.893572,143.91569,29.893572,143.91569);
                        ctx.bezierCurveTo(29.893572,143.91569,34.478622,73.319575,63.739168,73.319575);
                        ctx.bezierCurveTo(92.999759,73.319575,55.962041,142.42948,81.498551,144.65883);
                        ctx.bezierCurveTo(107.03503,146.88818,149.25942,78.527398,122.65893,77.041175);
                        ctx.bezierCurveTo(96.058441,75.554951,85.096643,140.94325,120.74129,143.1726);
                        ctx.bezierCurveTo(156.38598,145.40195,207.35821,31.603066,175.96961,28.630598);
                        ctx.bezierCurveTo(144.581,25.65813,143.41473,139.457,175.33529,142.42948);
                        ctx.bezierCurveTo(207.25592,145.40195,260.69587,26.76471,228.24325,24.535359);
                        ctx.bezierCurveTo(195.79064,22.306008,192.49628,138.33423,226.01293,139.07735);
                        ctx.bezierCurveTo(247.29334,137.59111,243.22956,72.57647,270.8941,74.062713);
                        ctx.bezierCurveTo(310.59618,77.372167,291.32616,150.90768,263.47925,141.68635);
                        ctx.bezierCurveTo(242.1714,134.06489,243.88478,72.584657,271.01731,74.0709);
                        ctx.bezierCurveTo(290.66644,76.633191,304.16617,102.41511,310.05704,83.78115);
                        ctx.stroke();

                        ctx.restore();
                    }
                }

                Image {
                    id: staticLogo
                    anchors.fill: parent
                    source: "InstallerHello.png"
                    fillMode: Image.PreserveAspectFit
                    sourceSize.width: 1120
                    sourceSize.height: 504
                    smooth: true
                    mipmap: true
                    opacity: installerWindow.logoAnimating ? 0 : 1
                    Behavior on opacity {
                        NumberAnimation { duration: 100 }
                    }
                }
            }

            // Installed version — sits low in the gap between logo and action
            // bar, outside the white card. The fillHeight spacer pushes it
            // down; a small bottom gap keeps it near the bar instead of
            // centred. Reads straight from the bridge's ``version`` property,
            // no network involved.
            Item { Layout.fillHeight: true }

            Text {
                Layout.alignment: Qt.AlignHCenter
                Layout.bottomMargin: 16
                text: installer ? installer.version : ""
                color: Kirigami.Theme.disabledTextColor
                font.family: installerWindow.fontFamily
                font.pointSize: Kirigami.Theme.defaultFont.pointSize * 0.9
            }
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
                            source: Qt.resolvedUrl(installerWindow.isDarkTheme
                                ? "InstallerGear-dark.svg" : "InstallerGear-light.svg")
                            sourceSize.width: 36
                            sourceSize.height: 36
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                        }
                    }
                }
            }
        }

        // ── installing view ──────────────────────────────────────────────
        // [ spinner ]  [ progress bar ] — centred as one row, macOS-style.
        Item {
            anchors.fill: parent
            visible: installerWindow.viewMode === "installing"

            Row {
                anchors.centerIn: parent
                spacing: 18

                // Indeterminate spinner: a quiet gray ring with a single blue
                // arc (same #007AFF as the progress fill) sweeping around it.
                // Canvas draws both strokes once; a RotationAnimator spins the
                // whole item so the blue arc orbits the ring continuously.
                Item {
                    id: spinner
                    width: 16
                    height: 16
                    anchors.verticalCenter: parent.verticalCenter

                    readonly property color ringColor: installerWindow.isDarkTheme
                        ? "#5A5A5E" : "#B0B0B8"
                    readonly property color arcColor: "#007AFF"
                    onRingColorChanged: spinnerCanvas.requestPaint()

                    Canvas {
                        id: spinnerCanvas
                        anchors.fill: parent
                        antialiasing: true
                        onPaint: {
                            const ctx = getContext("2d");
                            ctx.reset();
                            const cx = width / 2;
                            const cy = height / 2;
                            const lw = 2.5;
                            const r = Math.min(cx, cy) - lw;
                            ctx.lineCap = "round";
                            ctx.lineWidth = lw;
                            // Full gray track.
                            ctx.beginPath();
                            ctx.strokeStyle = spinner.ringColor;
                            ctx.arc(cx, cy, r, 0, 2 * Math.PI);
                            ctx.stroke();
                            // Blue sweep — a quarter-and-a-bit arc.
                            ctx.beginPath();
                            ctx.strokeStyle = spinner.arcColor;
                            ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 0.45);
                            ctx.stroke();
                        }
                    }

                    RotationAnimator {
                        target: spinner
                        running: installerWindow.viewMode === "installing"
                        from: 0
                        to: 360
                        duration: 900
                        loops: Animation.Infinite
                    }
                }

                Rectangle {
                    id: progressTrack
                    anchors.verticalCenter: parent.verticalCenter
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
                    ? "Uninstalled"
                    : "Installed"
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
