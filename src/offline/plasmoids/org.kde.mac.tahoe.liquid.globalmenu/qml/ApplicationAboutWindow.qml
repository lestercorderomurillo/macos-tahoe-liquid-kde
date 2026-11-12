// SPDX-License-Identifier: GPL-2.0-or-later
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.ki18n as KI18n

// Finder's About composition, with the selected application's own metadata.
// Keep a snapshot: focusing this window must not replace it with Plasma's data.
Window {
    id: root
    objectName: "applicationAboutWindow"
    property var applicationInfo: ({})
    readonly property string applicationName: applicationInfo.name || translations.i18n("Application")
    readonly property string location: applicationInfo.executable || applicationInfo.desktopFile || ""
    readonly property real unit: Kirigami.Units.gridUnit

    KI18n.KI18nContext {
        id: translations
        translationDomain: "plasma_applet_org.kde.mac.tahoe.liquid.globalmenu"
    }

    title: translations.i18n("About %1", applicationName)
    width: 20 * unit
    height: Math.min(22 * unit, Screen.height - 4 * unit)
    minimumWidth: width
    maximumWidth: width
    minimumHeight: height
    maximumHeight: height
    flags: Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint
    Kirigami.Theme.colorSet: Kirigami.Theme.View
    color: Kirigami.Theme.backgroundColor

    Shortcut { sequence: "Escape"; onActivated: root.close() }
    Shortcut { sequences: [StandardKey.Close]; onActivated: root.close() }

    function detailsText(): string {
        let rows = [applicationName];
        if (applicationInfo.description) rows.push(applicationInfo.description);
        for (const row of detailRows) {
            if (row.value) rows.push(row.label + ": " + row.value);
        }
        return rows.join("\n");
    }

    readonly property var detailRows: [
        { label: translations.i18n("Executable"), value: applicationInfo.executable || "" },
        { label: translations.i18n("Application ID"), value: applicationInfo.applicationId || "" },
        { label: translations.i18n("Desktop file"), value: applicationInfo.desktopFile || "" },
        { label: translations.i18n("Process ID"), value: applicationInfo.processId || "" }
    ]

    TextEdit {
        id: clipboard
        visible: false
        textFormat: TextEdit.PlainText
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.unit
        spacing: Kirigami.Units.smallSpacing

        QQC2.ScrollView {
            id: scroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth
            clip: true

            ColumnLayout {
                width: scroll.availableWidth
                spacing: 0

                Item { Layout.preferredHeight: root.unit }

                Kirigami.Icon {
                    objectName: "applicationIcon"
                    source: root.applicationInfo.icon || "application-x-executable"
                    implicitWidth: 6 * root.unit
                    implicitHeight: 6 * root.unit
                    Layout.alignment: Qt.AlignHCenter
                }

                Item { Layout.preferredHeight: 1.25 * root.unit }

                QQC2.Label {
                    objectName: "applicationName"
                    text: root.applicationName
                    textFormat: Text.PlainText
                    font.family: Kirigami.Theme.defaultFont.family
                    font.bold: true
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.15
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    horizontalAlignment: Text.AlignHCenter
                }

                QQC2.Label {
                    objectName: "applicationDescription"
                    visible: text.length > 0
                    text: root.applicationInfo.description || ""
                    textFormat: Text.PlainText
                    font: Kirigami.Theme.defaultFont
                    Layout.fillWidth: true
                    Layout.topMargin: Kirigami.Units.smallSpacing
                    wrapMode: Text.Wrap
                    horizontalAlignment: Text.AlignHCenter
                }

                Item { Layout.preferredHeight: root.unit }

                QQC2.Label {
                    text: translations.i18n("Location")
                    textFormat: Text.PlainText
                    font: Kirigami.Theme.smallFont
                    Layout.alignment: Qt.AlignHCenter
                    visible: root.location.length > 0
                }

                QQC2.TextArea {
                    objectName: "applicationLocation"
                    text: root.location || translations.i18n("Not Available")
                    textFormat: TextEdit.PlainText
                    readOnly: true
                    selectByMouse: true
                    font: Kirigami.Theme.defaultFont
                    color: Kirigami.Theme.textColor
                    horizontalAlignment: TextEdit.AlignHCenter
                    wrapMode: TextEdit.WrapAnywhere
                    Layout.fillWidth: true
                    background: null
                }

                QQC2.Label {
                    text: root.applicationInfo.applicationId || ""
                    visible: text.length > 0
                    textFormat: Text.PlainText
                    font: Kirigami.Theme.smallFont
                    color: Kirigami.Theme.disabledTextColor
                    Layout.fillWidth: true
                    Layout.topMargin: root.unit
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WrapAnywhere
                }
            }
        }

        QQC2.Button {
            objectName: "copyApplicationDetails"
            text: translations.i18n("Copy Details")
            Layout.alignment: Qt.AlignHCenter
            onClicked: {
                clipboard.text = root.detailsText();
                clipboard.selectAll();
                clipboard.copy();
                clipboard.deselect();
            }
        }
    }

    onApplicationInfoChanged: {
        // Reopening for another app also resets the previous scroll position.
        if (scroll.contentItem) scroll.contentItem.contentY = 0;
    }
}
