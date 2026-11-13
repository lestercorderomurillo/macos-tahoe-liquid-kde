import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid
import org.kde.plasma.components 3.0 as PC3
import org.kde.plasma.extras as PlasmaExtras

Item {

    function closeMenu() { contextMenu.close(); }

    readonly property bool menuOpen: contextMenu.status !== PlasmaExtras.Menu.Closed
    property color foregroundColor: main.textColor

    width: button.width
    height: button.height
    
    PC3.RoundButton {
        id: button
        Accessible.role: Accessible.ButtonMenu
        Accessible.name: i18n("Launcher options")

        flat: true
        // Make it look pressed while the menu is open
        down: contextMenu.status === PlasmaExtras.Menu.Open || pressed
        
        icon.name: "view-more-symbolic"
        icon.color: foregroundColor
        // Plasma's RoundButton icon uses its theme palette, not icon.color.
        Kirigami.Theme.textColor: foregroundColor

        background: Rectangle {
            color: button.down || (main.tahoeStyle && button.hovered) ? main.contrastBgColor : "transparent"
            border.width: main.tahoeStyle ? 1 : 0
            border.color: Qt.rgba(foregroundColor.r, foregroundColor.g, foregroundColor.b, 0.55)
            Behavior on color { ColorAnimation { duration: main.tahoeStyle ? 100 : 0 } }
            radius: height / 2
            scale: main.tahoeStyle ? 0.61 : 1
        }
        onPressed: contextMenu.openRelative()
    }

    PlasmaExtras.Menu {
        id: contextMenu
        visualParent: button
        placement: PlasmaExtras.Menu.BottomPosedLeftAlignedPopup

        PlasmaExtras.MenuItem {
            text: i18n("Preset 1 — Tahoe")
            checkable: true
            checked: kicker.launcherPreset === 1
            onClicked: Plasmoid.configuration.launcherPreset = 1
        }
        PlasmaExtras.MenuItem {
            text: i18n("Preset 2 — Golden Gate")
            checkable: true
            checked: kicker.launcherPreset === 2
            onClicked: Plasmoid.configuration.launcherPreset = 2
        }
        PlasmaExtras.MenuItem { separator: true }
        PlasmaExtras.MenuItem {
            text: i18n("Show apps in a list")
            checkable: true
            checked: Plasmoid.configuration.showAllAppsInList
            onClicked: {
                Plasmoid.configuration.showAllAppsInList = true;
                Plasmoid.configuration.showAllAppsInGrid = false;
            }
        }
        PlasmaExtras.MenuItem {
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
}
