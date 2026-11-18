/*
    SPDX-FileCopyrightText: 2013 Heena Mahour <heena393@gmail.com>
    SPDX-FileCopyrightText: 2013 Sebastian Kügler <sebas@kde.org>
    SPDX-FileCopyrightText: 2016 Kai Uwe Broulik <kde@privat.broulik.de>

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQml

import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.private.keyboardindicator as KeyboardIndicator
import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami
import org.kde.ksvg as KSvg
import plasma.applet.org.kde.mac.tahoe.liquid.globalmenu

PlasmoidItem {
    id: root

    readonly property bool vertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical
    readonly property bool view: Plasmoid.configuration.compactView
    readonly property string cfgIcon: Plasmoid.configuration.menuIcon || "start-here-kde-symbolic"

    readonly property real lightCapsuleOpacityBoost: material.hasElement("hint-clear-surface") ? 0 : 0.10

    KSvg.Svg {
        id: material
        imagePath: "dialogs/background"
    }

    Rectangle {
        id: barTint

        // Attach to the top panel window so the tint also sits behind its other applets.
        parent: Plasmoid.location === PlasmaCore.Types.TopEdge ? root.Window.window?.contentItem ?? null : null
        anchors.fill: parent
        visible: parent !== null
        z: -1

        readonly property bool lightText: Kirigami.ColorUtils.brightnessForColor(Kirigami.Theme.textColor)
                                          === Kirigami.ColorUtils.Light

        gradient: Gradient {
            GradientStop { position: 0; color: barTint.lightText ? "#29000000" : "#29ffffff" }
            GradientStop { position: 1; color: "transparent" }
        }
    }

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

        MenuDelegate {
            id: systemMenuButton
            lightCapsuleOpacityBoost: root.lightCapsuleOpacityBoost
            Accessible.name: i18n("System menu")
            readonly property int buttonIndex: -3
            menuIsOpen: Plasmoid.currentIndex !== -1

            Layout.fillHeight: !root.vertical

            topPadding: Kirigami.Units.smallSpacing
            bottomPadding: Kirigami.Units.smallSpacing
            leftPadding: 3.5 * Kirigami.Units.smallSpacing
            rightPadding: 3.5 * Kirigami.Units.smallSpacing

            down: Plasmoid.currentIndex === -3
            hoverOpensMenu: Plasmoid.configuration.hoverOpensMenu
            onActivated: Plasmoid.triggerSystemMenu(this)

            contentItem: Kirigami.Icon {
                source: root.cfgIcon
                implicitWidth: Kirigami.Units.iconSizes.small
                implicitHeight: Kirigami.Units.iconSizes.small
                color: Kirigami.Theme.textColor
            }
        }

        MenuDelegate {
            id: appNameButton
            lightCapsuleOpacityBoost: root.lightCapsuleOpacityBoost
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

                lightCapsuleOpacityBoost: root.lightCapsuleOpacityBoost
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
