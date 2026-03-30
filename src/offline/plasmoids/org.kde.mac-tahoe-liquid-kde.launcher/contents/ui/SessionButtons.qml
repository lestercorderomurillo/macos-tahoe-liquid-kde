import QtQuick
import org.kde.plasma.plasmoid
import org.kde.plasma.components 3.0 as PC3
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.private.kicker as Kicker
import org.kde.kitemmodels as KItemModels

Item {

    width: button.width
    height: button.height
    
    Kicker.SystemModel {
        id: systemModel
        favoritesModel: kicker.systemFavorites
    }

    component FilteredModel : KItemModels.KSortFilterProxyModel {
        sourceModel: systemModel

        function systemFavoritesContainsRow(sourceRow, sourceParent) {
            const FavoriteIdRole = sourceModel.KItemModels.KRoleNames.role("favoriteId");
            const favoriteId = sourceModel.data(sourceModel.index(sourceRow, 0, sourceParent), FavoriteIdRole);
            return String(Plasmoid.configuration.systemFavorites).includes(favoriteId);
        }

        function trigger(index) {
            const sourceIndex = mapToSource(this.index(index, 0));
            systemModel.trigger(sourceIndex.row, "", null);
        }

        Component.onCompleted: {
            Plasmoid.configuration.valueChanged.connect((key, value) => {
                if (key === "systemFavorites") {
                    invalidateFilter();
                }
            });
        }
    }

    FilteredModel {
        id: filteredButtonsModel
        filterRowCallback: (sourceRow, sourceParent) =>
            systemFavoritesContainsRow(sourceRow, sourceParent)
    }

    FilteredModel {
        id: filteredMenuItemsModel
        filterRowCallback: null
    }

    PC3.RoundButton {
        id: button
        Accessible.role: Accessible.ButtonMenu

        flat: true
        // Make it look pressed while the menu is open
        down: contextMenu.status === PlasmaExtras.Menu.Open || pressed
        
        icon.name: "system-shutdown"

        background: Rectangle {
            color: button.down ? main.contrastBgColor : "transparent"
            radius: height / 2
        }
        onPressed: contextMenu.openRelative()
    }

    Instantiator {
        model: filteredMenuItemsModel
        delegate: PlasmaExtras.MenuItem {
            required property int index
            required property var model

            text: model.display
            icon: model.decoration
            onClicked: {
                root.toggle();
                filteredMenuItemsModel.trigger(index);
            }
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
