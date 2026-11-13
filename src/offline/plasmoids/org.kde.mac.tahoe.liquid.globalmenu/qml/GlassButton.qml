// SPDX-License-Identifier: GPL-2.0-or-later
import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
QQC2.Button {
    property bool isDarkTheme: false
        id: control
        hoverEnabled: true
        implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                                implicitContentWidth + leftPadding + rightPadding)
        implicitHeight: Math.max(32, implicitContentHeight + topPadding + bottomPadding)
        leftPadding: 14
        rightPadding: 14
        topPadding: 6
        bottomPadding: 6

        contentItem: Text {
            style: Text.Raised
            styleColor: Qt.rgba(0, 0, 0, 0.12)
            objectName: "aboutButtonLabel"
            text: control.text
            font: control.font
            color: Kirigami.Theme.textColor
            opacity: control.enabled ? 1 : 0.4
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }

        background: Item {
            implicitWidth: 32
            implicitHeight: 32
            opacity: control.enabled ? 1 : 0.4

            Rectangle {
                anchors.fill: face
                anchors.topMargin: 0.8
                anchors.bottomMargin: -0.8
                radius: height / 2
                color: "transparent"
                border.width: 1
                border.color: Qt.rgba(0, 0, 0, control.isDarkTheme ? 28 / 255 : 12 / 255)
            }

            Rectangle {
                id: face
                objectName: "aboutButtonFace"
                anchors.fill: parent
                anchors.margins: 1
                anchors.bottomMargin: 2
                radius: height / 2
                color: control.down
                    ? (control.isDarkTheme ? Qt.rgba(1, 1, 1, 9 / 255) : Qt.rgba(0, 0, 0, 8 / 255))
                    : Qt.rgba(1, 1, 1, ((control.isDarkTheme ? 16 : 80) + (control.hovered ? 14 : 0)) / 255)
                border.width: 0.5
                border.color: control.isDarkTheme ? Qt.rgba(1, 1, 1, 24 / 255) : Qt.rgba(0, 0, 0, 22 / 255)
            }

            // Paint only the rim so the reflection never bands the glass face.
            Canvas {
                id: rim
                anchors.fill: face
                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()
                Connections {
                    target: control
                    function onIsDarkThemeChanged() { rim.requestPaint() }
                }
                onPaint: {
                    const ctx = getContext("2d");
                    ctx.reset();
                    const dark = control.isDarkTheme;
                    const gradient = ctx.createLinearGradient(0, 0, width, height);
                    const stops = [[0, dark ? 125 : 240], [.22, dark ? 65 : 160],
                                   [.44, 12], [.62, 6], [.84, dark ? 60 : 135],
                                   [1, dark ? 115 : 220]];
                    for (const stop of stops)
                        gradient.addColorStop(stop[0], Qt.rgba(1, 1, 1, stop[1] / 255));
                    ctx.strokeStyle = gradient;
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.roundedRect(.5, .5, width - 1, height - 1, (height - 1) / 2, (height - 1) / 2);
                    ctx.stroke();
                }
            }

            Rectangle {
                anchors.fill: face
                radius: height / 2
                color: "transparent"
                border.width: 1
                border.color: Kirigami.Theme.focusColor
                visible: control.visualFocus
            }
        }
    }

