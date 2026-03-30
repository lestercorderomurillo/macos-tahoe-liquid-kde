import QtQuick 2.12
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.0
import org.kde.draganddrop 2.0

ColumnLayout {
	id: allApps
	spacing: 0

	property QtObject allAppsModel: rootModel.modelForRow(2)
	property QtObject recentAppsModel
	property QtObject currentModel: rootModel.modelForRow(0)

	property var currentStateIndex: 0// Plasmoid.configuration.defaultPage

	property bool showItemsInGrid: plasmoid.configuration.showAllAppsInGrid
	property bool showItemsInList: plasmoid.configuration.showAllAppsInList 
	property bool showItemsCategorized: plasmoid.configuration.showAllAppsCategorized

	property Component preferredAppsViewComponent: showItemsInGrid ? applicationsGridViewComponent 
												: showItemsInList ? applicationsListViewComponent
												: applicationsCategorizedViewComponent

	property alias viewItem: appViewLoader.item

	property var appsCategoriesList: { 

		var categories = [];
		var categoryName;
		var categoryIcon;

		for (var i = 0; i < rootModel.count; i++) {
			categoryName  = rootModel.data(rootModel.index(i, 0), Qt.DisplayRole);
			categoryIcon  = rootModel.data(rootModel.index(i, 0), Qt.DecorationRole);

			// Rename "Recent Applications" / "Recent Documents" to "Suggestions"
			if (categoryName.toLowerCase().indexOf("recent") !== -1) {
				categoryName = "Suggestions";
			}

			categories.push({
				name: categoryName,
				modelIndex: i,
				icon: categoryIcon
			});
		}
		allApps.allAppsModel =  rootModel.modelForRow(2)
		allApps.currentModel =  rootModel.modelForRow(0)
		return categories;
	}

	property var slicedCategories: {
		// Keep Suggestions (index 0), skip "All Applications" (index 1), keep categories (2+)
		if (appsCategoriesList.length > 2) {
			return [appsCategoriesList[0]].concat(appsCategoriesList.slice(2));
		}
		return appsCategoriesList;
	}

	function updateShowedModel(index){
		currentModel = rootModel.modelForRow(index);
	}

	function reset(){
		currentStateIndex = 0
	}

	Connections {
		target: main

		function onShowAllAppsChanged() {
			// We can't show favorites/recent apps categorized
			if(showItemsCategorized) {
				plasmoid.configuration.showAllAppsCategorized = false;
				plasmoid.configuration.showAllAppsInList = true;
			}
		}
	}


	AppCategorySwitcher {
		id: categorySwitcher

		Layout.preferredWidth: parent.width-fs.innerPadding
    	Layout.preferredHeight: visible ? 40 : 0
		model: appsCategoriesList
		visible: !showItemsCategorized && main.showAllApps

		Component.onCompleted: {
			categorySwitcher.categorySwitched.connect(updateShowedModel)
		}
	}

	Loader {
		id: appViewLoader
		
		Layout.fillHeight: true		
		Layout.fillWidth: true
		
		sourceComponent: preferredAppsViewComponent
		active: true
	}

	onPreferredAppsViewComponentChanged: {
		appViewLoader.sourceComponent = preferredAppsViewComponent;
	}

	Component {
		id: applicationsListViewComponent
		AppListView {
			id: appList

			anchors.fill: parent

			showSectionSeparator: false

			model: main.showAllApps ? currentModel : globalFavorites
		}
	}

	Component {
		id: applicationsGridViewComponent

		AppGridView {
			id: grid
			anchors.fill: parent
			anchors.leftMargin: fs.innerPadding / 2
			
			model: main.showAllApps ? currentModel : globalFavorites
			canMoveWithKeyboard: true
			//viewItem.highlightFollowsCurrentItem: false
		}
	}

	Component {
		id: applicationsCategorizedViewComponent
		AppsCategorized {
			model: slicedCategories
			anchors.fill: parent
		}
	}

	Component.onCompleted: {
		allApps.recentAppsModel = rootModel.modelForRow(0);
	}
}
