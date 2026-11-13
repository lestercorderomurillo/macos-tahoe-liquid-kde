import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid
import org.kde.plasma.components 3.0 as PC3
import org.kde.plasma.extras as PlasmaExtras

Item {

    function closeMenu() { contextMenu.close(); tahoeMenu.close(); }
    readonly property var activeMenu: main.tahoeStyle ? tahoeMenu : contextMenu

    readonly property bool menuOpen: contextMenu.status !== PlasmaExtras.Menu.Closed || tahoeMenu.status !== PlasmaExtras.Menu.Closed
    property color foregroundColor: main.textColor

    width: button.width
    height: button.height
    
    PC3.RoundButton {
        id: button
        Accessible.role: Accessible.ButtonMenu
        Accessible.name: i18n("Launcher options")

        flat: true
        // Make it look pressed while the menu is open
        down: (main.tahoeStyle ? menuOpen : contextMenu.status === PlasmaExtras.Menu.Open) || pressed
        
        icon.name: "view-more-symbolic"
        icon.color: foregroundColor
        // Plasma's RoundButton icon uses its theme palette, not icon.color.
        Kirigami.Theme.textColor: foregroundColor

        // Preserve the native hit target; draw the reference-sized symbol inside it.
        Binding {
            target: button.contentItem
            property: "opacity"
            when: main.tahoeStyle
            value: 0
            restoreMode: Binding.RestoreBindingOrValue
        }
        Row {
            visible: main.tahoeStyle
            anchors.centerIn: parent
            spacing: 2.1
            Repeater {
                model: 3
                Rectangle {
                    width: 2.6
                    height: 2.6
                    radius: width / 2
                    color: foregroundColor
                }
            }
        }
        background: Item {
            Rectangle {
                anchors.centerIn: parent
                width: main.tahoeStyle ? 22 : parent.width
                height: main.tahoeStyle ? 22 : parent.height
                color: button.down || (main.tahoeStyle && button.hovered) ? main.contrastBgColor : "transparent"
                border.width: main.tahoeStyle ? 1.25 : 0
                border.color: Qt.rgba(foregroundColor.r, foregroundColor.g, foregroundColor.b, 0.85)
                Behavior on color { ColorAnimation { duration: main.tahoeStyle ? 100 : 0 } }
                radius: height / 2
            }
        }
        onPressed: activeMenu.openRelative()
        Item {
            id: tahoeMenuAnchor
            x: button.width + 10 - width
            width: 154
            y: button.height / 2 + 2
        }
    }

    PlasmaExtras.Menu {
        id: contextMenu
        visualParent: button
        placement: PlasmaExtras.Menu.BottomPosedLeftAlignedPopup

        PlasmaExtras.MenuItem {
            objectName: "preset1"
            text: i18n("Preset 1 — Tahoe")
            checkable: true
            checked: kicker.launcherPreset === 1
            onClicked: Plasmoid.configuration.launcherPreset = 1
        }
        PlasmaExtras.MenuItem {
            objectName: "preset2"
            text: i18n("Preset 2 — Golden Gate")
            checkable: true
            checked: kicker.launcherPreset === 2
            onClicked: Plasmoid.configuration.launcherPreset = 2
        }
        PlasmaExtras.MenuItem { separator: true }
        PlasmaExtras.MenuItem {
            objectName: "list"
            text: i18n("Show apps in a list")
            checkable: true
            checked: Plasmoid.configuration.showAllAppsInList
            onClicked: {
                Plasmoid.configuration.showAllAppsInList = true;
                Plasmoid.configuration.showAllAppsInGrid = false;
            }
        }
        PlasmaExtras.MenuItem {
            objectName: "grid"
            text: i18n("Show apps in a grid")
            checkable: true
            checked: !Plasmoid.configuration.showAllAppsInList
            onClicked: {
                Plasmoid.configuration.showAllAppsInList = false;
                Plasmoid.configuration.showAllAppsInGrid = true;
            }
        }
        onStatusChanged: {
            if ( contextMenu.status === PlasmaExtras.Menu.Closed && Qt.application.layoutDirection == Qt.LeftToRight) {
                nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)
            }
        }   
    }
    TahoeOptionsMenu {
        id: tahoeMenu
        anchorItem: tahoeMenuAnchor

        actions: [
        PlasmaExtras.MenuItem { text: i18n("View content as"); section: true },
        PlasmaExtras.MenuItem {
            objectName: "grid"
            text: i18n("Grid")
            checkable: true
            checked: !Plasmoid.configuration.showAllAppsInList
            onClicked: {
                Plasmoid.configuration.showAllAppsInList = false;
                Plasmoid.configuration.showAllAppsInGrid = true;
            }
        },
        PlasmaExtras.MenuItem {
            objectName: "list"
            text: i18n("List")
            checkable: true
            checked: Plasmoid.configuration.showAllAppsInList
            onClicked: {
                Plasmoid.configuration.showAllAppsInList = true;
                Plasmoid.configuration.showAllAppsInGrid = false;
            }
        },
        PlasmaExtras.MenuItem { separator: true },
        PlasmaExtras.MenuItem { text: i18n("Launcher preset"); section: true },
        PlasmaExtras.MenuItem {
            objectName: "preset1"
            text: i18n("Tahoe")
            checkable: true
            checked: kicker.launcherPreset === 1
            onClicked: Plasmoid.configuration.launcherPreset = 1
        },
        PlasmaExtras.MenuItem {
            objectName: "preset2"
            text: i18n("Golden Gate")
            checkable: true
            checked: kicker.launcherPreset === 2
            onClicked: Plasmoid.configuration.launcherPreset = 2
        }
        ]
    }
}
