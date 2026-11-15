// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
ColumnLayout {
    id: page
    property string title
    spacing: Kirigami.Units.smallSpacing * 2
    Layout.minimumWidth: 250
    Layout.preferredWidth: 300
    Layout.maximumWidth: 400
    Layout.minimumHeight: implicitHeight
    Layout.maximumHeight: implicitHeight
    Kirigami.Heading { visible: text.length > 0; text: page.title; level: 4; font.family: "SF Pro Text"; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true }
}
