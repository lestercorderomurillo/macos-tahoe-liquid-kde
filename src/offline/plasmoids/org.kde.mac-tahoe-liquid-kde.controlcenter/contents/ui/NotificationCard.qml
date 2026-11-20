// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.kquickcontrolsaddons as KQuickAddons
import org.kde.notificationmanager as Notifications
import org.kde.plasma.extras as PlasmaExtras
import QtQml.Models
import "NotificationContrast.js" as Contrast

Item {
    id: row
    objectName: "notificationCard"
    required property var model
    required property int index
    required property var history
    property var previewHistory: history
    property int previewRevision: 0
    function refreshPreview() { Qt.callLater(function() { ++row.previewRevision; }); }
    Connections {
        target: row.previewHistory
        ignoreUnknownSignals: true
        function onCountChanged() { row.refreshPreview(); }
        function onDataChanged() { row.refreshPreview(); }
        function onModelReset() { row.refreshPreview(); }
    }
    property bool compact: false
    property bool replying: false
    readonly property bool lightMode: Kirigami.Theme.textColor.r * 0.2126 + Kirigami.Theme.textColor.g * 0.7152 + Kirigami.Theme.textColor.b * 0.0722 < 0.5
    property color backdropColor: "transparent"
    property color surfaceColor: "transparent"
    readonly property color foregroundColor: Contrast.foreground(Kirigami.Theme.textColor,
        backdropColor, surfaceColor)
    readonly property bool hovered: hover.hovered
    readonly property bool interacting: hovered || dismiss.hovered || reply.activeFocus || options.visible
    readonly property bool closeVisible: dismiss.opacity > 0
    implicitWidth: 316
    implicitHeight: content.implicitHeight
    HoverHandler { id: hover }
    function itemIndex() { return history.index(index, 0); }
    function open() {
        if (model.isGroup) history.setData(itemIndex(), !model.isGroupExpanded, Notifications.Notifications.IsGroupExpandedRole);
        else if (model.hasDefaultAction) history.invokeDefaultAction(itemIndex());
    }

    // Measurements are in logical pixels, from Apple's 2x notification captures.
    // The application icon is centred against the whole text block, not its header.
    ColumnLayout {
        id: content
        width: parent.width
        spacing: 8
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Item {
                Layout.preferredWidth: 32
                Layout.preferredHeight: 32
                Layout.alignment: Qt.AlignVCenter
                Kirigami.Icon {
                    x: -3; y: -2; width: 36; height: 36
                    visible: !row.model.image
                    source: row.model.applicationIconName || row.model.iconName || "application-x-executable"
                    fallback: "application-x-executable"
                }
                Loader {
                    x: -3; y: -2; width: 36; height: 36
                    active: !!row.model.image
                    sourceComponent: KQuickAddons.QImageItem {
                        image: row.model.image
                        fillMode: KQuickAddons.QImageItem.PreserveAspectFit
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                ControlLabel {
                    objectName: "notificationApplicationName"
                    Layout.fillWidth: true
                    text: /^discord$/i.test(row.model.applicationName || "") ? "Discord" : row.model.applicationName || ""
                    visible: text.length > 0
                    color: row.foregroundColor
                    font.family: "SF Pro Display"; font.pixelSize: 13; font.weight: Font.DemiBold
                    lineHeightMode: Text.FixedHeight; lineHeight: 16
                    elide: Text.ElideRight
                }
                ControlLabel {
                    Layout.fillWidth: true
                    objectName: "notificationSummary"
                    text: row.model.summary || ""
                    visible: (!row.model.isGroup || !row.model.isGroupExpanded) && text.length > 0
                    textFormat: Text.PlainText
                    color: row.foregroundColor
                    font.family: "SF Pro Display"; font.pixelSize: 13; font.weight: Font.DemiBold
                    lineHeightMode: Text.FixedHeight; lineHeight: 16
                    maximumLineCount: 1; elide: Text.ElideRight
                }
                ControlLabel {
                    id: description
                    objectName: "notificationBody"
                    Layout.fillWidth: true
                    readonly property int restingLines: Math.min(measure.lineCount, row.compact || row.model.isGroup ? 2 : 100)
                    Layout.preferredHeight: restingLines * 16
                    text: {
                        // Read the aggregate role as well, so a new message in
                        // an existing collapsed group refreshes its preview.
                        const body = row.model.body || "";
                        const revision = row.previewRevision;
                        if (!row.model.isGroup || row.model.isGroupExpanded) return body;
                        for (let i = 0; i < row.previewHistory.count; ++i) {
                            const index = row.previewHistory.index(i, 0);
                            if (String(row.previewHistory.data(index, Notifications.Notifications.IdRole)) === String(row.model.notificationId))
                                return row.previewHistory.data(index, Notifications.Notifications.BodyRole) || "";
                        }
                        return "";
                    }
                    visible: (!row.model.isGroup || !row.model.isGroupExpanded) && text.length > 0
                    textFormat: Text.StyledText
                    color: row.foregroundColor
                    font.family: "SF Pro Display"; font.pixelSize: 13; font.weight: Font.Normal
                    lineHeightMode: Text.FixedHeight; lineHeight: 16
                    wrapMode: Text.WordWrap
                    maximumLineCount: restingLines
                    rightPadding: more.visible ? more.width + 4 : 0
                    elide: Text.ElideRight
                    onLinkActivated: link => Qt.openUrlExternally(link)
                    Text {
                        id: measure
                        visible: false
                        width: description.width; text: description.text
                        font: description.font; textFormat: description.textFormat
                        wrapMode: Text.WordWrap
                        lineHeightMode: Text.FixedHeight; lineHeight: 16
                    }
                }
            }
        }
        QQC.ProgressBar {
            Layout.fillWidth: true
            visible: row.model.type === Notifications.Notifications.JobType
            from: 0; to: 100; value: row.model.percentage || 0
        }
        RowLayout {
            Layout.fillWidth: true
            visible: !!row.model.hasReplyAction && row.replying
            QQC.TextField {
                id: reply
                objectName: "notificationReply"
                Layout.fillWidth: true
                font.family: "SF Pro Text"; font.pixelSize: 13
                placeholderText: i18n("Reply…")
                Accessible.name: placeholderText
            }
            QQC.Button {
                objectName: "notificationSend"
                font.family: "SF Pro Text"; font.pixelSize: 13
                text: i18n("Send")
                enabled: reply.text.trim().length > 0
                onClicked: {
                    row.history.reply(row.itemIndex(), reply.text, Notifications.Notifications.None);
                    reply.clear(); row.replying = false;
                }
            }
        }
    }
    MouseArea {
        anchors.fill: parent
        z: -1
        acceptedButtons: Qt.LeftButton
        onClicked: row.open()
        cursorShape: row.model.hasDefaultAction || row.model.isGroup ? Qt.PointingHandCursor : Qt.ArrowCursor
    }
    QQC.AbstractButton {
        id: dismiss
        objectName: "notificationDismiss"
        // The surface supplies 14px left and 12px top padding. The reference's
        // 20px close disc starts 6px left and 4px above the surface itself.
        x: -20; y: -16
        width: 20; height: 20
        z: 2
        visible: !!row.model.closable
        opacity: row.hovered || hovered || activeFocus ? 1 : 0
        Accessible.name: i18n("Dismiss")
        background: Rectangle {
            radius: 10
            color: Kirigami.Theme.textColor.r < 0.5
                ? Qt.rgba(1, 1, 1, dismiss.hovered ? 0.85 : 0.65)
                : Qt.rgba(0.22, 0.22, 0.22, dismiss.hovered ? 0.95 : 0.85)
            border.width: 0.5
            border.color: Qt.rgba(1, 1, 1, 0.35)
        }
        contentItem: Kirigami.Icon {
            source: Qt.resolvedUrl("symbols/mttkde-control-notification-close.svg")
            isMask: true
            color: Kirigami.Theme.textColor
            opacity: dismiss.hovered ? 0.85 : 0.65
        }
        onClicked: row.history.close(row.itemIndex())
    }
    QQC.ToolButton {
        id: more
        objectName: "notificationOptionsButton"
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: -4; anchors.bottomMargin: -2
        width: 78; height: 22
        visible: row.hovered || dismiss.hovered || hovered || options.visible
        text: i18n("Options")
        font.family: "SF Pro Display"; font.pixelSize: 13
        horizontalPadding: 9
        contentItem: RowLayout {
            spacing: 4
            Text {
                text: more.text; font: more.font
                color: row.foregroundColor
                Layout.alignment: Qt.AlignVCenter
            }
            Kirigami.Icon {
                source: Qt.resolvedUrl("symbols/mttkde-control-notification-options.svg")
                isMask: true
                color: row.foregroundColor
                Layout.preferredWidth: 12; Layout.preferredHeight: 12
                Layout.alignment: Qt.AlignVCenter
            }
        }
        background: Rectangle {
            radius: 11
            color: Kirigami.Theme.textColor.r < 0.5 ? Qt.rgba(0, 0, 0, more.hovered ? 0.16 : 0.09)
                                                       : Qt.rgba(1, 1, 1, more.hovered ? 0.22 : 0.12)
        }
        onClicked: options.openRelative()
    }
    MacOptionsMenu {
        id: options
        objectName: "notificationOptionsMenu"
        anchorItem: more
        textColor: Kirigami.Theme.textColor
        preferredWidth: 184
        fitContents: true
        property var applicationActions: []
        actions: [groupAction, openAction].concat(applicationActions,
            [replyAction, pauseAction, cancelAction, settingsAction])
        onRestoreFocusRequested: more.forceActiveFocus()

        property QtObject groupAction: PlasmaExtras.MenuItem {
            objectName: "notificationGroup"
            text: row.model.isGroupExpanded ? i18n("Collapse") : i18n("Expand")
            visible: !!row.model.isGroup
            onClicked: row.history.setData(row.itemIndex(), !row.model.isGroupExpanded, Notifications.Notifications.IsGroupExpandedRole)
        }
        property QtObject openAction: PlasmaExtras.MenuItem {
            objectName: "notificationOpen"; text: i18n("Open")
            visible: !!row.model.hasDefaultAction
            onClicked: row.open()
        }
        property Instantiator actionObjects: Instantiator {
            model: row.model.actionNames || []
            delegate: PlasmaExtras.MenuItem {
                objectName: "notificationAction"
                required property string modelData
                required property int index
                text: row.model.actionLabels[index] || modelData
                onClicked: row.history.invokeAction(row.itemIndex(), modelData)
            }
            onObjectAdded: (index, object) => {
                const actions = options.applicationActions.slice();
                actions.splice(index, 0, object);
                options.applicationActions = actions;
            }
            onObjectRemoved: (index, object) => {
                const actions = options.applicationActions.slice();
                actions.splice(index, 1);
                options.applicationActions = actions;
            }
        }
        property QtObject replyAction: PlasmaExtras.MenuItem {
            objectName: "notificationReplyAction"
            text: i18n("Reply…")
            visible: !!row.model.hasReplyAction
            onClicked: { row.replying = true; reply.forceActiveFocus(); }
        }
        property QtObject pauseAction: PlasmaExtras.MenuItem {
            objectName: "notificationPause"
            text: row.model.jobState === Notifications.Notifications.JobStateSuspended ? i18n("Resume") : i18n("Pause")
            visible: !!row.model.suspendable
            onClicked: row.model.jobState === Notifications.Notifications.JobStateSuspended ? row.history.resumeJob(row.itemIndex()) : row.history.suspendJob(row.itemIndex())
        }
        property QtObject cancelAction: PlasmaExtras.MenuItem {
            objectName: "notificationCancel"; text: i18n("Cancel Job")
            visible: !!row.model.killable
            onClicked: row.history.killJob(row.itemIndex())
        }
        property QtObject settingsAction: PlasmaExtras.MenuItem {
            objectName: "notificationSettings"
            text: i18n("Notification Settings…")
            onClicked: preferences.clicked()
        }
    }

    SettingsLink { id: preferences; visible: false; module: "kcm_notifications" }
}
