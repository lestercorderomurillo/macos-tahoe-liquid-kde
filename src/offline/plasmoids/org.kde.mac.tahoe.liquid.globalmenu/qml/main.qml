/*
    SPDX-FileCopyrightText: 2013 Heena Mahour <heena393@gmail.com>
    SPDX-FileCopyrightText: 2013 Sebastian Kügler <sebas@kde.org>
    SPDX-FileCopyrightText: 2016 Kai Uwe Broulik <kde@privat.broulik.de>

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtQml

import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.private.keyboardindicator as KeyboardIndicator
import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami
import plasma.applet.org.kde.mac.tahoe.liquid.globalmenu

PlasmoidItem {
    id: root

    readonly property bool vertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical
    readonly property bool view: Plasmoid.configuration.compactView
    readonly property string cfgIcon: Plasmoid.configuration.menuIcon || "start-here-kde-symbolic"

    AboutWindow {
        id: aboutWindow
        useSystemFont: Plasmoid.configuration.useSystemFont
    }

    ApplicationAboutWindow {
        id: applicationAboutWindow
    }

    Connections {
        target: Plasmoid
        function onAboutRequested() {
            aboutWindow.show();
            aboutWindow.raise();
            aboutWindow.requestActivate();
        }
        function onApplicationAboutRequested(info) {
            applicationAboutWindow.applicationInfo = info;
            applicationAboutWindow.show();
            applicationAboutWindow.raise();
            applicationAboutWindow.requestActivate();
        }
    }

    Component.onCompleted: Plasmoid.view = view

    onViewChanged: {
        Plasmoid.view = view;
    }

    Plasmoid.constraintHints: Plasmoid.CanFillArea
    preferredRepresentation: Plasmoid.configuration.compactView ? compactRepresentation : fullRepresentation

    compactRepresentation: PlasmaComponents3.ToolButton {
        readonly property int fakeIndex: 0
        Layout.fillWidth: false
        Layout.fillHeight: false
        Layout.minimumWidth: implicitWidth
        Layout.maximumWidth: implicitWidth
        enabled: appMenuModel.menuAvailable
        checkable: appMenuModel.menuAvailable && Plasmoid.currentIndex === fakeIndex
        checked: checkable
        icon.name: "application-menu"

        display: PlasmaComponents3.AbstractButton.IconOnly
        text: Plasmoid.title
        Accessible.description: root.toolTipSubText

        onClicked: Plasmoid.trigger(this, 0);
    }

    fullRepresentation: GridLayout {
        id: buttonGrid

        Plasmoid.status: {
            if (Plasmoid.currentIndex !== -1) {
                return PlasmaCore.Types.NeedsAttentionStatus;
            }
            return PlasmaCore.Types.ActiveStatus;
        }

        LayoutMirroring.enabled: Application.layoutDirection === Qt.RightToLeft
        Layout.minimumWidth: implicitWidth
        Layout.minimumHeight: implicitHeight

        flow: root.vertical ? GridLayout.TopToBottom : GridLayout.LeftToRight
        rowSpacing: 0
        columnSpacing: 0

        Binding {
            target: Plasmoid
            property: "buttonGrid"
            value: buttonGrid
            restoreMode: Binding.RestoreNone
        }

        Connections {
            target: Plasmoid
            function onRequestActivateIndex(index: int) {
                if (index === -3) {
                    Plasmoid.triggerSystemMenu(systemMenuButton);
                } else if (index === -2) {
                    appNameButton.activated();
                } else {
                    const button = buttonRepeater.itemAt(index) as MenuDelegate;
                    if (button) {
                        button.activated();
                    }
                }
            }
        }

        Connections {
            target: Plasmoid
            function onActivated() {
                const button = buttonRepeater.itemAt(0) as MenuDelegate;
                if (button) {
                    button.activated();
                }
            }
        }

        QQC2.AbstractButton {
            id: systemMenuButton
            Accessible.name: i18n("System menu")
            readonly property int buttonIndex: -3
            property bool menuIsOpen: Plasmoid.currentIndex !== -1

            Layout.fillHeight: !root.vertical

            topPadding: Kirigami.Units.smallSpacing
            bottomPadding: Kirigami.Units.smallSpacing
            leftPadding: 3.5 * Kirigami.Units.smallSpacing
            rightPadding: 3.5 * Kirigami.Units.smallSpacing

            hoverEnabled: true
            onHoveredChanged: if (Plasmoid.configuration.hoverOpensMenu && hovered && menuIsOpen) { Plasmoid.triggerSystemMenu(this); }
            onPressed: Plasmoid.triggerSystemMenu(this)

            down: Plasmoid.currentIndex === -3

            property int menuState: {
                if (down) return 2;
                if (hovered && !menuIsOpen) return 1;
                return 0;
            }

            background: Rectangle {
                y: Math.min(Kirigami.Units.smallSpacing, systemMenuButton.height / 4)
                height: Math.max(0, systemMenuButton.height - 2 * y)
                radius: Math.min(width, height) / 2
                color: systemMenuButton.menuState === 0
                       ? "transparent"
                       : Qt.rgba(0.5, 0.5, 0.5, systemMenuButton.menuState === 2 ? 0.25 : 0.18)
            }

            contentItem: Kirigami.Icon {
                source: root.cfgIcon
                implicitWidth: Kirigami.Units.iconSizes.small
                implicitHeight: Kirigami.Units.iconSizes.small
                color: Kirigami.Theme.textColor
            }
        }

        MenuDelegate {
            id: appNameButton
            readonly property int buttonIndex: -2
            visible: appMenuModel.activeAppName !== ""
            text: appMenuModel.activeAppName
            font.weight: Font.Bold
            Layout.fillHeight: !root.vertical

            down: Plasmoid.currentIndex === -2
            hoverOpensMenu: Plasmoid.configuration.hoverOpensMenu
            menuIsOpen: Plasmoid.currentIndex !== -1
            onActivated: Plasmoid.triggerWindowMenu(this)
        }

        Repeater {
            id: buttonRepeater
            model: appMenuModel.visible ? appMenuModel : null

            MenuDelegate {
                required property int index
                required property string activeMenu
                required property PlasmaCore.Action activeActions
                readonly property int buttonIndex: index

                Layout.fillWidth: root.vertical
                Layout.fillHeight: !root.vertical
                text: activeMenu
                Kirigami.MnemonicData.active: altState.pressed

                down: Plasmoid.currentIndex === index
                visible: text !== "" && (activeActions?.visible ?? false)
                enabled: activeActions?.enabled ?? false

                hoverOpensMenu: Plasmoid.configuration.hoverOpensMenu
                menuIsOpen: Plasmoid.currentIndex !== -1
                onActivated: Plasmoid.trigger(this, index)

                KeyboardIndicator.KeyState {
                    id: altState
                    key: Qt.Key_Alt
                }
            }
        }
        Item {
            Layout.preferredWidth: 0
            Layout.preferredHeight: 0
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }

    AppMenuModel {
        id: appMenuModel
        containmentStatus: Plasmoid.containment.status
        screenGeometry: root.screenGeometry
        allScreens: Plasmoid.configuration.allScreens
        enableGenericMenu: Plasmoid.configuration.enableGenericMenu
        enableMenuSearch: Plasmoid.configuration.enableMenuSearch
        onRequestActivateIndex: Plasmoid.requestActivateIndex(index)
        Component.onCompleted: {
            Plasmoid.model = appMenuModel;
        }
    }
}
