// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
QQC.ToolButton {
    id: button
    display: QQC.AbstractButton.IconOnly
    Accessible.name: text
    contentItem: Kirigami.Icon {
        isMask: true
        implicitWidth: button.icon.width > 0 ? button.icon.width : 20
        implicitHeight: button.icon.height > 0 ? button.icon.height : 20
        source: button.icon.source.toString().length ? button.icon.source : button.icon.name
        color: Kirigami.Theme.textColor
        opacity: button.enabled ? 1 : 0.35
    }
}
