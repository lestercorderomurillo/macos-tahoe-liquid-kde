// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "NotificationContrast.js" as Contrast
import org.kde.kirigami as Kirigami

ControlLabel {
    id: label
    property bool floating: false
    property color backdropColor: "transparent"
    color: floating
        ? Contrast.foreground(Kirigami.Theme.textColor, backdropColor, Qt.rgba(0,0,0,0))
        : Contrast.preferredText(Kirigami.Theme.textColor)
    font.family: "SF Pro Display"; font.pixelSize: 13
}
