import QtQuick
import org.kde.plasma.plasmoid
import org.kde.plasma.components 3.0 as PC3
import org.kde.plasma.extras as PlasmaExtras

Item {

    width: button.width
    height: button.height
    
    property var menuModel: [
        {
            title: i18n("Show apps in a list"),
            action: () => {
                plasmoid.configuration.showAllAppsInList = true;
                plasmoid.configuration.showAllAppsInGrid = false;
                plasmoid.configuration.showAllAppsCategorized = false;
            },
            checked: plasmoid.configuration.showAllAppsInList,
            enabled: true
        }, 
        {
            title: i18n("Show apps in a grid"),
            action: () => {
                plasmoid.configuration.showAllAppsInList = false;
                plasmoid.configuration.showAllAppsInGrid = true;
                plasmoid.configuration.showAllAppsCategorized = false;
            },
            checked: plasmoid.configuration.showAllAppsInGrid,
             enabled: true
        },
        {
            title: i18n("Show apps categorized"),
           action: () => {
                plasmoid.configuration.showAllAppsInList = false;
                plasmoid.configuration.showAllAppsInGrid = false;
                plasmoid.configuration.showAllAppsCategorized = true;
            },
            checked:  plasmoid.configuration.showAllAppsCategorized,
            enabled: main.showAllApps
        }
    ]

    PC3.RoundButton {
        id: button
        Accessible.role: Accessible.ButtonMenu

        flat: true
        // Make it look pressed while the menu is open
        down: contextMenu.status === PlasmaExtras.Menu.Open || pressed
        
        icon.name: "application-menu" 

        background: Rectangle {
            color: button.down ? main.contrastBgColor : "transparent"
            radius: height / 2
        }
        onPressed: contextMenu.openRelative()
    }

    Instantiator {
        model: menuModel
        delegate: PlasmaExtras.MenuItem {
            required property int index
            required property var model

            icon: model.checked ? "checkmark-symbolic" : ""
            checked: model.checked
            text: model.title
            enabled: model.enabled
            // icon: model.decoration
            onClicked: model.action()
        }
        onObjectAdded: (index, object) => contextMenu.addMenuItem(object)
        onObjectRemoved: (index, object) => contextMenu.removeMenuItem(object)
    }

    PlasmaExtras.Menu {
        id: contextMenu
        visualParent: button
        placement: PlasmaExtras.Menu.BottomPosedLeftAlignedPopup
        onStatusChanged: {
            if ( contextMenu.status === PlasmaExtras.Menu.Closed && Qt.application.layoutDirection == Qt.LeftToRight) {
                nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)
            }
        }   
    }
}
