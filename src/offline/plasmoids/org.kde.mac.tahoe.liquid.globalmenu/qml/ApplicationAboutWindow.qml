// SPDX-License-Identifier: GPL-2.0-or-later
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.ki18n as KI18n
import org.kde.ksvg as KSvg
import org.kde.plasma.plasma5support as P5Support

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
    flags: Qt.Window | Qt.FramelessWindowHint
    Kirigami.Theme.colorSet: Kirigami.Theme.View
    color: "transparent"

    property var windowControlPaths: ({})
    readonly property string windowControlPath: windowControlPaths[isDarkTheme ? "Dark" : "Light"] || ""
    property string controlsCommand: "sh -c 'PATH=\"$HOME/.local/bin:$PATH\" mac-tahoe-about-info --window-controls'"

    P5Support.DataSource {
        id: controlsSource
        engine: "executable"
        connectedSources: []
        onNewData: (sourceName, data) => {
            disconnectSource(sourceName);
            try {
                root.windowControlPaths = JSON.parse(data["stdout"] || "{}");
            } catch (e) {
                root.windowControlPaths = {};
            }
        }
    }
    function refreshWindowControls() {
        if (visible && controlsSource && controlsSource.connectedSources.indexOf(controlsCommand) < 0)
            controlsSource.connectSource(controlsCommand);
    }
    onActiveChanged: {
        if (active)
            refreshWindowControls();
    }
    onIsDarkThemeChanged: refreshWindowControls()

    readonly property bool isDarkTheme: {
        let bg = Kirigami.Theme.backgroundColor;
        return (bg.r * 0.299 + bg.g * 0.587 + bg.b * 0.114) < 0.5;
    }

    onVisibleChanged: { if (visible) refreshWindowControls() }

    KSvg.Svg {
        id: popupSurface
        imagePath: "dialogs/background"
        property bool clearSurface: false
        onRepaintNeeded: clearSurface = hasElement("hint-clear-surface")
        Component.onCompleted: clearSurface = hasElement("hint-clear-surface")
    }

    // The SVG hint identifies Golden Gate, not a permanently clear fill.
    // Its light surface must back dark text even over a black glass backdrop.
    Rectangle {
        id: glass
        objectName: "aboutGlassSurface"
        anchors.fill: parent
        radius: 22
        color: popupSurface.clearSurface ? Qt.rgba(1, 1, 1, root.isDarkTheme ? 0.01 : 0.60)
            : root.isDarkTheme ? Qt.rgba(0, 0, 0, 0.48) : Qt.rgba(1, 1, 1, 0.55)
        border.width: 0.75
        border.color: Qt.rgba(0, 0, 0, 0.18)

        Rectangle {
            objectName: "aboutGlassHighlight"
            anchors.fill: parent
            anchors.margins: 0.75
            radius: glass.radius - 0.75
            color: "transparent"
            border.width: 0.75
            border.color: Qt.rgba(1, 1, 1, 0.22)
        }

        layer.enabled: true

        // Let the compositor move the frameless window on Wayland and X11.
        MouseArea {
            objectName: "aboutDragArea"
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton
            onPressed: root.startSystemMove()
        }

        // window buttons
        Row {
            anchors { left: parent.left; top: parent.top; leftMargin: 14; topMargin: 14 }
            spacing: 8
            z: 1

            Repeater {
                model: ["close", "minimize", "maximize"]
                delegate: Item {
                    id: light
                    objectName: "rootLight-" + modelData
                    required property string modelData
                    width: 16; height: 16
                    readonly property bool actionable: modelData === "close"
                    readonly property bool artworkAvailable: buttonSvg.imagePath.length > 0 && buttonSvg.isValid()
                    KSvg.Svg {
                        id: buttonSvg
                        imagePath: root.windowControlPath
                            ? root.windowControlPath + "/" + light.modelData + ".svg" : ""
                    }
                    KSvg.SvgItem {
                        objectName: "rootLightImage-" + light.modelData
                        anchors.fill: parent
                        svg: buttonSvg
                        elementId: (!light.actionable ? "deactivated" :
                            !root.active ? "inactive" : closeTap.pressed ? "pressed" :
                            closeHover.hovered ? "hover" : "active") + "-center"
                        visible: light.artworkAvailable
                    }
                    Rectangle {
                        anchors.centerIn: parent
                        width: 14; height: 14; radius: 7
                        visible: !light.artworkAvailable
                        color: light.actionable && root.active ? "#FF5F57" :
                            root.isDarkTheme ? Qt.rgba(1, 1, 1, 0.2) : Qt.rgba(0, 0, 0, 0.12)
                        border.width: 0.5
                        border.color: Qt.rgba(0, 0, 0, 0.12)
                        Text {
                            anchors.centerIn: parent
                            text: "×"; color: Qt.rgba(0, 0, 0, 0.5)
                            font.pixelSize: 11; font.bold: true
                            visible: light.actionable && closeHover.hovered && root.active
                        }
                    }
                    HoverHandler { id: closeHover; enabled: light.actionable }
                    TapHandler { id: closeTap; enabled: light.actionable; onTapped: root.close() }
                }
            }
        }

        Item { id: content; anchors.fill: parent; anchors.topMargin: 28 }
    }

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
        parent: content
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

        GlassButton {
            isDarkTheme: root.isDarkTheme
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
