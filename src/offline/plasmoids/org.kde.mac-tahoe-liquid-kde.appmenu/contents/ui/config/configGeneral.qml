/*
    SPDX-FileCopyrightText: 2020 Kpple <info.kpple@gmail.com>
    SPDX-FileCopyrightText: 2024 Christian Tallner <chrtall@gmx.de>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtQuick.Dialogs

import org.kde.plasma.core as PlasmaCore
import org.kde.ksvg as KSvg
import org.kde.iconthemes as KIconThemes
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM
import org.kde.config as KConfig
import org.kde.plasma.plasmoid

import "../code/tools.js" as Tools


KCM.SimpleKCM {
    id: root

    property string cfg_icon: Plasmoid.configuration.icon
    property string cfg_toolTipTitle: Plasmoid.configuration.toolTipTitle
    property string cfg_toolTipSubText: Plasmoid.configuration.toolTipSubText
    property string cfg_menuItems: Plasmoid.configuration.menuItems

    property var menuItemsList: {
        try {
            return JSON.parse(cfg_menuItems)
        } catch (e) {
            return []
        }
    }

    function saveMenuItems() {
        cfg_menuItems = JSON.stringify(menuItemsList)
    }

    function moveItem(fromIndex, toIndex) {
        if (toIndex < 0 || toIndex >= menuItemsList.length) return
        var items = menuItemsList.slice()
        var item = items.splice(fromIndex, 1)[0]
        items.splice(toIndex, 0, item)
        menuItemsList = items
        saveMenuItems()
    }

    function removeItem(index) {
        var items = menuItemsList.slice()
        items.splice(index, 1)
        menuItemsList = items
        saveMenuItems()
    }

    function addItem(type, name, command, shortcut) {
        var items = menuItemsList.slice()
        if (type === "divider") {
            items.push({"type": "divider"})
        } else {
            var newItem = {"type": "item", "name": name || "New Item", "command": command || ""}
            if (shortcut) newItem.shortcut = shortcut
            items.push(newItem)
        }
        menuItemsList = items
        saveMenuItems()
    }

    function updateItem(index, name, command, shortcut) {
        var items = menuItemsList.slice()
        if (items[index].type === "item") {
            items[index].name = name
            items[index].command = command
            if (shortcut) {
                items[index].shortcut = shortcut
            } else {
                delete items[index].shortcut
            }
        }
        menuItemsList = items
        saveMenuItems()
    }

    Kirigami.FormLayout {
        QQC2.Button {
            id: iconButton

            Kirigami.FormData.label: i18n("Icon:")

            implicitWidth: previewFrame.width + Kirigami.Units.smallSpacing * 2
            implicitHeight: previewFrame.height + Kirigami.Units.smallSpacing * 2
            hoverEnabled: true

            KIconThemes.IconDialog {
                id: iconDialog
                onIconNameChanged: (iconName) => {
                    root.cfg_icon = iconName || Tools.defaultIconName
                }
            }

            onPressed: iconMenu.opened ? iconMenu.close() : iconMenu.open()

            KSvg.FrameSvgItem {
                id: previewFrame
                anchors.centerIn: parent
                imagePath: plasmoid.formFactor === PlasmaCore.Types.Vertical || plasmoid.formFactor === PlasmaCore.Types.Horizontal
                    ? "widgets/panel-background" : "widgets/background"
                width: Kirigami.Units.iconSizes.large + fixedMargins.left + fixedMargins.right
                height: Kirigami.Units.iconSizes.large + fixedMargins.top + fixedMargins.bottom

                Kirigami.Icon {
                    anchors.centerIn: parent
                    width: Kirigami.Units.iconSizes.large
                    height: Kirigami.Units.iconSizes.large
                    source: Tools.iconOrDefault(plasmoid.formFactor, root.cfg_icon)
                }
            }

            QQC2.Menu {
                id: iconMenu
                y: parent.height

                QQC2.MenuItem {
                    text: i18n("Choose...")
                    icon.name: "document-open-folder"
                    onClicked: iconDialog.open()
                }
                QQC2.MenuItem {
                    text: i18n("Reset to default icon")
                    icon.name: "edit-clear"
                    enabled: root.cfg_icon !== Tools.defaultIconName
                    onClicked: root.cfg_icon = Tools.defaultIconName
                }
                QQC2.MenuItem {
                    text: i18n("Remove icon")
                    icon.name: "delete"
                    enabled: root.cfg_icon !== "" && plasmoid.formFactor !== PlasmaCore.Types.Vertical
                    onClicked: root.cfg_icon = ""
                }
            }
        }

        QQC2.TextField {
            Kirigami.FormData.label: i18n("Tooltip title:")
            Layout.preferredWidth: 300
            text: root.cfg_toolTipTitle
            onTextChanged: root.cfg_toolTipTitle = text
        }

        QQC2.TextField {
            Kirigami.FormData.label: i18n("Tooltip description:")
            Layout.preferredWidth: 300
            text: root.cfg_toolTipSubText
            onTextChanged: root.cfg_toolTipSubText = text
        }

        Item {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: i18n("Menu Items")
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing

            QQC2.Frame {
                Layout.fillWidth: true
                Layout.preferredHeight: 300

                ListView {
                    id: menuListView
                    anchors.fill: parent
                    anchors.margins: 1
                    model: root.menuItemsList
                    clip: true
                    spacing: 2

                    delegate: QQC2.ItemDelegate {
                        required property var modelData
                        required property int index
                        width: menuListView.width
                        height: modelData.type === "divider" ? Kirigami.Units.gridUnit * 1.5 : Kirigami.Units.gridUnit * 2.5

                        highlighted: menuListView.currentIndex === index

                        onClicked: menuListView.currentIndex = index

                        onDoubleClicked: {
                            if (modelData.type === "item") {
                                editDialog.itemIndex = index
                                editDialog.itemName = modelData.name || ""
                                editDialog.itemCommand = modelData.command || ""
                                editDialog.itemShortcut = modelData.shortcut || ""
                                editDialog.open()
                            }
                        }

                        contentItem: RowLayout {
                            spacing: Kirigami.Units.smallSpacing

                            Rectangle {
                                visible: modelData.type === "divider"
                                Layout.fillWidth: true
                                Layout.alignment: Qt.AlignVCenter
                                height: 1
                                color: Kirigami.Theme.disabledTextColor
                            }

                            ColumnLayout {
                                visible: modelData.type === "item"
                                Layout.fillWidth: true
                                spacing: 0

                                QQC2.Label {
                                    Layout.fillWidth: true
                                    text: modelData.name || i18n("Unnamed")
                                    elide: Text.ElideRight
                                }

                                QQC2.Label {
                                    Layout.fillWidth: true
                                    text: modelData.command || ""
                                    elide: Text.ElideRight
                                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                                    color: Kirigami.Theme.disabledTextColor
                                }
                            }

                            QQC2.Label {
                                visible: modelData.shortcut ? true : false
                                text: modelData.shortcut || ""
                                color: Kirigami.Theme.disabledTextColor
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                QQC2.Button {
                    icon.name: "list-add"
                    text: i18n("Add Item")
                    onClicked: {
                        editDialog.itemIndex = -1
                        editDialog.itemName = ""
                        editDialog.itemCommand = ""
                        editDialog.itemShortcut = ""
                        editDialog.open()
                    }
                }

                QQC2.Button {
                    icon.name: "distribute-horizontal-center"
                    text: i18n("Add Divider")
                    onClicked: root.addItem("divider")
                }

                Item { Layout.fillWidth: true }

                QQC2.Button {
                    icon.name: "go-up"
                    enabled: menuListView.currentIndex > 0
                    onClicked: {
                        var idx = menuListView.currentIndex
                        root.moveItem(idx, idx - 1)
                        menuListView.currentIndex = idx - 1
                    }
                    QQC2.ToolTip.text: i18n("Move Up")
                    QQC2.ToolTip.visible: hovered
                }

                QQC2.Button {
                    icon.name: "go-down"
                    enabled: menuListView.currentIndex >= 0 && menuListView.currentIndex < root.menuItemsList.length - 1
                    onClicked: {
                        var idx = menuListView.currentIndex
                        root.moveItem(idx, idx + 1)
                        menuListView.currentIndex = idx + 1
                    }
                    QQC2.ToolTip.text: i18n("Move Down")
                    QQC2.ToolTip.visible: hovered
                }

                QQC2.Button {
                    icon.name: "edit-entry"
                    enabled: menuListView.currentIndex >= 0 && root.menuItemsList[menuListView.currentIndex] && root.menuItemsList[menuListView.currentIndex].type === "item"
                    onClicked: {
                        var idx = menuListView.currentIndex
                        var item = root.menuItemsList[idx]
                        editDialog.itemIndex = idx
                        editDialog.itemName = item.name || ""
                        editDialog.itemCommand = item.command || ""
                        editDialog.itemShortcut = item.shortcut || ""
                        editDialog.open()
                    }
                    QQC2.ToolTip.text: i18n("Edit")
                    QQC2.ToolTip.visible: hovered
                }

                QQC2.Button {
                    icon.name: "list-remove"
                    enabled: menuListView.currentIndex >= 0
                    onClicked: {
                        root.removeItem(menuListView.currentIndex)
                        if (menuListView.currentIndex >= root.menuItemsList.length) {
                            menuListView.currentIndex = root.menuItemsList.length - 1
                        }
                    }
                    QQC2.ToolTip.text: i18n("Remove")
                    QQC2.ToolTip.visible: hovered
                }
            }

            QQC2.Label {
                Layout.fillWidth: true
                text: i18n("Double-click an item to edit it")
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                color: Kirigami.Theme.disabledTextColor
            }
        }
    }

    QQC2.Dialog {
        id: editDialog
        title: itemIndex === -1 ? i18n("Add Menu Item") : i18n("Edit Menu Item")
        modal: true
        standardButtons: QQC2.Dialog.Ok | QQC2.Dialog.Cancel
        anchors.centerIn: parent

        property int itemIndex: -1
        property string itemName: ""
        property string itemCommand: ""
        property string itemShortcut: ""

        onAccepted: {
            if (itemIndex === -1) {
                root.addItem("item", nameField.text, commandField.text, shortcutField.text)
            } else {
                root.updateItem(itemIndex, nameField.text, commandField.text, shortcutField.text)
            }
        }

        onOpened: {
            nameField.text = itemName
            commandField.text = itemCommand
            shortcutField.text = itemShortcut
            nameField.forceActiveFocus()
        }

        contentItem: Kirigami.FormLayout {
            QQC2.TextField {
                id: nameField
                Kirigami.FormData.label: i18n("Name:")
                placeholderText: i18n("Menu item name")
                Layout.preferredWidth: 300
            }

            QQC2.TextField {
                id: commandField
                Kirigami.FormData.label: i18n("Command:")
                placeholderText: i18n("Command to execute")
                Layout.preferredWidth: 300
            }

            QQC2.TextField {
                id: shortcutField
                Kirigami.FormData.label: i18n("Shortcut label (optional):")
                placeholderText: i18n("e.g. ⌃⌘Q")
                Layout.preferredWidth: 300
            }
        }
    }
}
