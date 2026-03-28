/*
    SPDX-FileCopyrightText: 2025 MacTahoe Liquid KDE
    SPDX-License-Identifier: LGPL-3.0-or-later
*/

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami
import org.kde.iconthemes as KIconThemes

Kirigami.FormLayout {
    id: configPage

    property alias cfg_iconEmpty: iconEmptyField.text
    property alias cfg_iconFull: iconFullField.text

    RowLayout {
        Kirigami.FormData.label: i18nc("@label:textbox", "Empty trash icon:")
        spacing: Kirigami.Units.smallSpacing

        QQC2.Button {
            implicitWidth: Kirigami.Units.iconSizes.large + Kirigami.Units.largeSpacing
            implicitHeight: implicitWidth

            Kirigami.Icon {
                anchors.centerIn: parent
                width: Kirigami.Units.iconSizes.large
                height: width
                source: cfg_iconEmpty || "user-trash"
            }

            onClicked: iconDialogEmpty.open()

            QQC2.ToolTip.text: i18nc("@info:tooltip", "Click to choose icon")
            QQC2.ToolTip.visible: hovered
        }

        QQC2.TextField {
            id: iconEmptyField
            Layout.fillWidth: true
            placeholderText: "user-trash"
        }
    }

    RowLayout {
        Kirigami.FormData.label: i18nc("@label:textbox", "Full trash icon:")
        spacing: Kirigami.Units.smallSpacing

        QQC2.Button {
            implicitWidth: Kirigami.Units.iconSizes.large + Kirigami.Units.largeSpacing
            implicitHeight: implicitWidth

            Kirigami.Icon {
                anchors.centerIn: parent
                width: Kirigami.Units.iconSizes.large
                height: width
                source: cfg_iconFull || "user-trash-full"
            }

            onClicked: iconDialogFull.open()

            QQC2.ToolTip.text: i18nc("@info:tooltip", "Click to choose icon")
            QQC2.ToolTip.visible: hovered
        }

        QQC2.TextField {
            id: iconFullField
            Layout.fillWidth: true
            placeholderText: "user-trash-full"
        }
    }

    KIconThemes.IconDialog {
        id: iconDialogEmpty
        onIconNameChanged: (iconName) => {
            if (iconName) {
                cfg_iconEmpty = iconName;
            }
        }
    }

    KIconThemes.IconDialog {
        id: iconDialogFull
        onIconNameChanged: (iconName) => {
            if (iconName) {
                cfg_iconFull = iconName;
            }
        }
    }
}
