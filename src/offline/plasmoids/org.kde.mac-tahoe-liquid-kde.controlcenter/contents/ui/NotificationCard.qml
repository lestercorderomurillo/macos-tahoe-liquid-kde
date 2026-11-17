// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC
import org.kde.kirigami as Kirigami
import org.kde.kquickcontrolsaddons as KQuickAddons
import org.kde.notificationmanager as Notifications

Item {
    id: row
    objectName: "notificationCard"
    required property var model
    required property int index
    required property var history
    property bool compact: false
    property bool replying: false
    readonly property bool lightMode: Kirigami.Theme.textColor.r * 0.2126 + Kirigami.Theme.textColor.g * 0.7152 + Kirigami.Theme.textColor.b * 0.0722 < 0.5
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
                    Layout.fillWidth: true
                    text: row.model.applicationName || ""
                    visible: text.length > 0
                    color: row.lightMode ? "black" : Kirigami.Theme.textColor
                    font.family: "SF Pro Display"; font.pixelSize: 13; font.weight: Font.DemiBold
                    lineHeightMode: Text.FixedHeight; lineHeight: 16
                    elide: Text.ElideRight
                }
                ControlLabel {
                    Layout.fillWidth: true
                    text: row.model.summary || ""
                    visible: (!row.model.isGroup || !row.model.isGroupExpanded) && text.length > 0
                    textFormat: Text.PlainText
                    color: row.lightMode ? "black" : Kirigami.Theme.textColor
                    font.family: "SF Pro Display"; font.pixelSize: 13; font.weight: Font.DemiBold
                    lineHeightMode: Text.FixedHeight; lineHeight: 16
                    maximumLineCount: 1; elide: Text.ElideRight
                }
                ControlLabel {
                    id: description
                    Layout.fillWidth: true
                    readonly property int restingLines: Math.min(measure.lineCount, row.compact || row.model.isGroup ? 2 : 100)
                    Layout.preferredHeight: restingLines * 16
                    text: {
                        // Read the aggregate role as well, so a new message in
                        // an existing collapsed group refreshes its preview.
                        const body = row.model.body || "";
                        return row.model.isGroup && !row.model.isGroupExpanded
                            ? row.history.data(row.history.index(row.index + 1, 0), Notifications.Notifications.BodyRole) || ""
                            : body;
                    }
                    visible: (!row.model.isGroup || !row.model.isGroupExpanded) && text.length > 0
                    textFormat: Text.StyledText
                    color: row.lightMode ? "black" : Kirigami.Theme.textColor
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
                color: row.lightMode ? "black" : Kirigami.Theme.textColor
                Layout.alignment: Qt.AlignVCenter
            }
            Kirigami.Icon {
                source: Qt.resolvedUrl("symbols/mttkde-control-notification-options.svg")
                isMask: true
                color: row.lightMode ? "black" : Kirigami.Theme.textColor
                Layout.preferredWidth: 12; Layout.preferredHeight: 12
                Layout.alignment: Qt.AlignVCenter
            }
        }
        background: Rectangle {
            radius: 11
            color: Kirigami.Theme.textColor.r < 0.5 ? Qt.rgba(0, 0, 0, more.hovered ? 0.16 : 0.09)
                                                       : Qt.rgba(1, 1, 1, more.hovered ? 0.22 : 0.12)
        }
        onClicked: options.open()
        QQC.Menu {
            id: options
            y: more.height + 4
            font.family: "SF Pro Display"; font.pixelSize: 13
            QQC.MenuItem {
                objectName: "notificationGroup"
                text: row.model.isGroupExpanded ? i18n("Collapse") : i18n("Expand")
                visible: !!row.model.isGroup
                height: visible ? implicitHeight : 0
                onTriggered: row.history.setData(row.itemIndex(), !row.model.isGroupExpanded, Notifications.Notifications.IsGroupExpandedRole)
            }
            QQC.MenuItem {
                objectName: "notificationOpen"; text: i18n("Open")
                visible: !!row.model.hasDefaultAction
                height: visible ? implicitHeight : 0
                onTriggered: row.open()
            }
            Repeater {
                model: row.model.actionNames || []
                QQC.MenuItem {
                    objectName: "notificationAction"
                    required property string modelData
                    required property int index
                    text: row.model.actionLabels[index] || modelData
                    onTriggered: row.history.invokeAction(row.itemIndex(), modelData)
                }
            }
            QQC.MenuItem {
                text: i18n("Reply…")
                visible: !!row.model.hasReplyAction
                height: visible ? implicitHeight : 0
                onTriggered: { row.replying = true; reply.forceActiveFocus(); }
            }
            QQC.MenuItem {
                objectName: "notificationPause"
                text: row.model.jobState === Notifications.Notifications.JobStateSuspended ? i18n("Resume") : i18n("Pause")
                visible: !!row.model.suspendable
                height: visible ? implicitHeight : 0
                onTriggered: row.model.jobState === Notifications.Notifications.JobStateSuspended ? row.history.resumeJob(row.itemIndex()) : row.history.suspendJob(row.itemIndex())
            }
            QQC.MenuItem {
                objectName: "notificationCancel"; text: i18n("Cancel Job")
                visible: !!row.model.killable
                height: visible ? implicitHeight : 0
                onTriggered: row.history.killJob(row.itemIndex())
            }
            QQC.MenuItem {
                text: i18n("Notification Settings…")
                onTriggered: preferences.clicked()
            }
        }
    }
    SettingsLink { id: preferences; visible: false; module: "kcm_notifications" }
}
