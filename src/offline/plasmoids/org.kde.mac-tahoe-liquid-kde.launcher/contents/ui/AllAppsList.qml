import QtQuick 2.12
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.0
import org.kde.draganddrop 2.0
import org.kde.plasma.private.kicker as Kicker

ColumnLayout {
	id: allApps
	spacing: 0

	property QtObject allAppsModel
	property QtObject recentAppsModel
	property QtObject currentModel: rootModel.modelForRow(0)

	property var currentStateIndex: 0// Plasmoid.configuration.defaultPage

	property bool showItemsInList: plasmoid.configuration.showAllAppsInList
	property bool showItemsInGrid: !showItemsInList

	// In grid mode the "All Applications" tab shows the categorized
	// sections; every other tab (Favorites, Suggestions, a single
	// category) is a plain grid. List mode is always a flat list.
	property bool selectedIsAllApps: {
		var pos = categorySwitcher.currentIndex;
		return pos >= 0 && pos < appsCategoriesList.length
			&& appsCategoriesList[pos].isAllApps;
	}

	property Component preferredAppsViewComponent:
		showItemsInList ? applicationsListViewComponent
		: selectedIsAllApps && !main.detachedSearch ? applicationsCategorizedViewComponent
		: applicationsGridViewComponent

	property alias viewItem: appViewLoader.item

	property var appsCategoriesList: {

		var categories = [];
		var categoryName;
		var categoryIcon;
		var allAppsFound = null;

		// Favorites is not a rootModel row; modelIndex -1 marks it.
		// Reading count here keeps the list reactive to fav changes.
		if (globalFavorites && globalFavorites.count > 0) {
			categories.push({
				name: i18n("Favorites"),
				modelIndex: -1,
				icon: "favorite",
				isAllApps: false,
				isFavorites: true,
				isSuggestions: false
			});
		}

		for (var i = 0; i < rootModel.count; i++) {
			categoryName  = rootModel.data(rootModel.index(i, 0), Qt.DisplayRole);
			categoryIcon  = rootModel.data(rootModel.index(i, 0), Qt.DecorationRole);
			var sub = rootModel.modelForRow(i);

			// Skip anything empty or broken: separators (blank name,
			// null model) and 0-item categories. sub.count is a live
			// dependency — an empty Suggestions row reappears the
			// moment recents exist.
			if (!sub || !categoryName || categoryName.trim() === "" || !sub.count) {
				continue;
			}

			var isAllApps = (sub.description === "KICKER_ALL_MODEL");
			if (isAllApps) {
				allAppsFound = sub;
				categoryName = i18n("Apps");
			}

			var isSuggestions = sub instanceof Kicker.RecentUsageModel;
			if (isSuggestions) {
				categoryName = i18n("Suggestions");
			}

			categories.push({
				name: categoryName,
				modelIndex: i,
				icon: categoryIcon,
				isAllApps: isAllApps,
				isFavorites: false,
				isSuggestions: isSuggestions
			});
		}
		allApps.allAppsModel = allAppsFound;
		return categories;
	}

	// Selected category's modelIndex; survives list rebuilds (e.g. the
	// Favorites section appearing). null = pick the first category.
	property var selectedModelIndex: null

	onAppsCategoriesListChanged: syncSelection()
	Connections {
		target: main
		function onDetachedSearchChanged() { Qt.callLater(allApps.syncSelection); }
	}

	function syncSelection() {
		if (!appsCategoriesList.length) {
			return;
		}
		var pos = 0;
		for (var i = 0; i < appsCategoriesList.length; i++) {
			if (appsCategoriesList[i].modelIndex === selectedModelIndex
				|| (selectedModelIndex === null && main.detachedSearch && appsCategoriesList[i].isAllApps)) {
				pos = i;
				break;
			}
		}
		categorySwitcher.currentIndex = pos;
		currentModel = modelForCategory(appsCategoriesList[pos]);
	}

	property var slicedCategories: {
		// Sections shown inside the "All Applications" tab: every real
		// app category. Favorites, Suggestions and the All-Apps entry
		// itself are their own tabs, so drop them here.
		return appsCategoriesList.filter(function (c) {
			return !c.isAllApps && !c.isFavorites
				&& !c.isSuggestions;
		});
	}

	function modelForCategory(category) {
		return category.isFavorites ? globalFavorites
			: rootModel.modelForRow(category.modelIndex);
	}

	function updateShowedModel(index){
		selectedModelIndex = index;
		currentModel = (index === -1) ? globalFavorites
			: rootModel.modelForRow(index);
	}

	function reset(){
		currentStateIndex = 0
	}

	AppCategorySwitcher {
		id: categorySwitcher

		Layout.preferredWidth: parent.width - (main.detachedSearch ? 0 : fs.innerPadding)
		Layout.preferredHeight: visible ? Math.max(main.categoryHeight, implicitHeight) : 0
		Layout.minimumHeight: Layout.preferredHeight
		model: appsCategoriesList
		visible: true

		Component.onCompleted: {
			categorySwitcher.categorySwitched.connect(updateShowedModel)
		}
	}

	// Separator below the tabs, mirroring the one above them in
	// MainView so the capsule row sits between two lines.
	Rectangle {
		visible: !main.detachedSearch
		Layout.fillWidth: true
		Layout.rightMargin: fs.innerPadding
		Layout.topMargin: 6
		Layout.bottomMargin: 6
		height: 1.5
		color: main.contrastBgColor
	}

	Loader {
		id: appViewLoader
		
		Layout.fillHeight: true		
		Layout.fillWidth: true
		Layout.topMargin: main.gridTopSpacing
		
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

			model: currentModel
		}
	}

	Component {
		id: applicationsGridViewComponent

		AppGridView {
			id: grid
			anchors.fill: parent
			anchors.leftMargin: main.detachedSearch ? 0 : fs.innerPadding / 2
			
			model: currentModel
			canMoveWithKeyboard: true
			showFavorites: main.detachedSearch && allApps.selectedIsAllApps
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
		syncSelection();
	}
}
