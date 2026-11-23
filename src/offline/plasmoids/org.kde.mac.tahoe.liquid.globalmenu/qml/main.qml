/*
    SPDX-FileCopyrightText: 2013 Heena Mahour <heena393@gmail.com>
    SPDX-FileCopyrightText: 2013 Sebastian Kügler <sebas@kde.org>
    SPDX-FileCopyrightText: 2016 Kai Uwe Broulik <kde@privat.broulik.de>

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import QtQml

import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.private.keyboardindicator as KeyboardIndicator
import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami
import org.kde.mac.tahoe.launcher as Native
import org.kde.ksvg as KSvg
import plasma.applet.org.kde.mac.tahoe.liquid.globalmenu

PlasmoidItem {
    id: root

    readonly property bool wallpaperTint: Plasmoid.location === PlasmaCore.Types.TopEdge
    readonly property bool vertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical
    readonly property bool view: Plasmoid.configuration.compactView
    readonly property string cfgIcon: Plasmoid.configuration.menuIcon || "start-here-symbolic"

    readonly property bool goldenGate: material.hasElement("hint-clear-surface")
    readonly property real lightCapsuleOpacityBoost: goldenGate ? 0 : 0.10

    KSvg.Svg {
        id: material
        imagePath: "dialogs/background"
    }

    Rectangle {
        id: barTint

        // Paint in the panel window behind the existing menu and status applets.
        parent: root.wallpaperTint ? root.Window.window?.contentItem ?? null : null
        anchors.fill: parent
        visible: parent !== null
        opacity: root.Window.window?.visible && visible ? 1 : 0
        z: -1

        Behavior on opacity {
            enabled: barTint.visible
            NumberAnimation { duration: 110; easing.type: Easing.OutExpo }
        }

        // The effect uses these same logical dimensions for pointer motion.
        readonly property real cornerExtent: visible && root.Window.window?.visible
            && Math.abs(width - root.screenGeometry.width) < 1 ? Math.min(10, height / 3) : 0
        readonly property real cornerControlFraction: 0.19
        Native.GlassSettings {
            window: barTint.cornerExtent > 0 ? root.Window.window : null
            displayCorners: Qt.size(barTint.cornerExtent, barTint.cornerControlFraction)
        }

        Native.PanelWallpaper { id: scrim }
        function scrimColor(position: real): color {
            return Qt.rgba(0, 0, 0, scrim.scrimOpacityAt(position))
        }

        // Share the rendered stops with the wallpaper contrast sampler.
        gradient: Gradient {
            GradientStop { position: 0; color: barTint.scrimColor(0) }
            GradientStop { position: 0.125; color: barTint.scrimColor(0.125) }
            GradientStop { position: 0.25; color: barTint.scrimColor(0.25) }
            GradientStop { position: 0.375; color: barTint.scrimColor(0.375) }
            GradientStop { position: 0.5; color: barTint.scrimColor(0.5) }
            GradientStop { position: 0.625; color: barTint.scrimColor(0.625) }
            GradientStop { position: 0.75; color: barTint.scrimColor(0.75) }
            GradientStop { position: 0.875; color: barTint.scrimColor(0.875) }
            GradientStop { position: 1; color: "transparent" }
        }

        Repeater {
            model: barTint.cornerExtent > 0 ? 2 : 0

            delegate: Shape {
                id: corner
                required property int index
                readonly property real extent: barTint.cornerExtent
                x: index === 0 ? 0 : barTint.width - width
                width: extent
                height: extent
                antialiasing: true
                preferredRendererType: Shape.CurveRenderer
                transform: Scale {
                    origin.x: corner.width / 2
                    xScale: corner.index === 0 ? 1 : -1
                }

                ShapePath {
                    fillColor: "#f20e1117"
                    strokeWidth: -1
                    startX: 0
                    startY: 0
                    PathLine { x: corner.extent; y: 0 }
                    PathCubic {
                        x: 0; y: corner.extent
                        control1X: corner.extent * barTint.cornerControlFraction; control1Y: 0
                        control2X: 0; control2Y: corner.extent * barTint.cornerControlFraction
                    }
                    PathLine { x: 0; y: 0 }
                }
            }
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

    component TopBarDelegate: MenuDelegate {
        id: button
        foregroundColor: ink.foreground
        Native.WallpaperInk {
            id: ink
            item: button
            base: button.baseForeground
            active: root.wallpaperTint
        }
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
            function onRequestActivateIndex(index: int, navigationOnly: bool) {
                if (index === -3) {
                    Plasmoid.triggerSystemMenu(systemMenuButton);
                } else if (index === -2) {
                    appNameButton.activated(navigationOnly);
                } else {
                    const button = buttonRepeater.itemAt(index) as MenuDelegate;
                    if (button) {
                        button.activated(navigationOnly);
                    }
                }
            }
        }

        Connections {
            target: Plasmoid
            function onActivated() {
                const button = buttonRepeater.itemAt(0) as MenuDelegate;
                if (button) {
                    button.activated(false);
                }
            }
        }

        TopBarDelegate {
            id: systemMenuButton
            baseForeground: Kirigami.Theme.textColor
            horizontalBar: !root.vertical
            goldenGate: root.goldenGate
            lightCapsuleOpacityBoost: root.lightCapsuleOpacityBoost
            Accessible.name: i18n("System menu")
            readonly property int buttonIndex: -3
            menuIsOpen: Plasmoid.currentIndex !== -1

            Layout.fillHeight: !root.vertical

            topPadding: Kirigami.Units.smallSpacing
            bottomPadding: Kirigami.Units.smallSpacing
            Layout.leftMargin: root.vertical ? 0 : 6.5
            Layout.rightMargin: root.vertical ? 0 : 1
            leftPadding: root.vertical ? 3.5 * Kirigami.Units.smallSpacing : 7.1
            rightPadding: root.vertical ? 3.5 * Kirigami.Units.smallSpacing : 7.3

            down: Plasmoid.currentIndex === -3
            hoverOpensMenu: Plasmoid.configuration.hoverOpensMenu
            onActivated: Plasmoid.triggerSystemMenu(this)

            contentItem: Item {
                implicitWidth: root.vertical ? Kirigami.Units.iconSizes.small : 18
                implicitHeight: implicitWidth
                Kirigami.Icon {
                    anchors.centerIn: parent
                    width: parent.implicitWidth
                    height: width
                    roundToIconSize: root.vertical
                    source: root.cfgIcon
                    color: systemMenuButton.foregroundColor
                }
            }
        }

        TopBarDelegate {
            id: appNameButton
            horizontalBar: !root.vertical
            goldenGate: root.goldenGate
            lightCapsuleOpacityBoost: root.lightCapsuleOpacityBoost
            readonly property int buttonIndex: -2
            visible: appMenuModel.activeAppName !== ""
            text: appMenuModel.activeAppName
            font.weight: Font.ExtraBold
            Layout.fillHeight: !root.vertical

            down: Plasmoid.currentIndex === -2
            hoverOpensMenu: Plasmoid.configuration.hoverOpensMenu
            menuIsOpen: Plasmoid.currentIndex !== -1
            onActivated: Plasmoid.triggerWindowMenu(this)
        }

        Repeater {
            id: buttonRepeater
            model: appMenuModel.visible ? appMenuModel : null

            TopBarDelegate {
                required property int index
                required property string activeMenu
                required property PlasmaCore.Action activeActions
                readonly property int buttonIndex: index

                horizontalBar: !root.vertical
                goldenGate: root.goldenGate
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
                onActivated: (navigationOnly) => Plasmoid.trigger(this, index, navigationOnly)

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
        onRequestActivateIndex: Plasmoid.requestActivateIndex(index, false)
        Component.onCompleted: {
            Plasmoid.model = appMenuModel;
        }
    }
}
