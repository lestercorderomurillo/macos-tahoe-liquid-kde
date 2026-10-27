import QtQuick
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components 3.0 as PlasmaComponents
import org.kde.coreaddons as KCoreAddons

import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami
import org.kde.mac.tahoe.launcher as Tahoe

import "js/colorType.js" as ColorType

Item {
	id: main
	readonly property bool goldenGateEdition: false
	readonly property bool goldenGateLight: goldenGateEdition && !isDarkTheme
	property string searchText: ""
	readonly property bool searching: searchText !== ""
	readonly property var searchBar: detachedSearch ? detachedSearchBar : inlineSearchBar
	onSearchTextChanged: runnerModel.query = searchText
	readonly property bool detachedSearch: kicker.launcherPreset === 2
	readonly property real searchPopupHeight: searchPopup.height
	readonly property real searchPopupGap: Kirigami.Units.gridUnit * 0.75
	readonly property real categoryHeight: detachedSearch ? Kirigami.Units.gridUnit * 16 / 9 : 40
	readonly property real gridTopSpacing: detachedSearch ? Kirigami.Units.gridUnit * 16 / 9 : 0
	// QWindow.active also includes transient parents/siblings, such as the panel.
	readonly property bool popupHasFocus: {
		var window = searchPopup.focusWindow;
		while (window) {
			if (window === root || (searchPopup.visible && window === searchPopup)) {
				return true;
			}
			// Include our context menus, but never the panel or its other popups.
			window = window.transientParent;
		}
		return false;
	}
	onPopupHasFocusChanged: root.checkDismissal()
	readonly property bool menuOpen: searchBar.menuOpen

	function focusSearch() {
		if (detachedSearch) {
			searchPopup.activate();
		} else {
			root.requestActivate();
		}
		searchBar.textField.forceActiveFocus(Qt.PopupFocusReason);
	}

	onDetachedSearchChanged: {
		inlineSearchBar.closeMenu();
		detachedSearchBar.closeMenu();
		Qt.callLater(function() {
			root.reposition();
			if (root.visible) {
				focusSearch();
			}
		});
	}
	onSearchPopupHeightChanged: root.reposition()
	onMenuOpenChanged: {
		if (!menuOpen && root.visible) {
			root.checkDismissal();
		}
	}

	Tahoe.LauncherSearchPopup {
		id: searchPopup
		objectName: "launcherSearchPopup"
		visualParent: root.contentItem
		popupDirection: Qt.TopEdge
		margin: main.searchPopupGap
		transientParent: root
		visible: root.visible && main.detachedSearch
		// PopupPlasmaWindow stays open by default. Its hideOnWindowDeactivate
		// property only exists in Plasma 6.7+; our focus group handles dismissal.
		width: root.width * 0.617
		height: Kirigami.Units.iconSizes.huge * 1.625

		mainItem: FocusScope {
			id: detachedSearchSlot
			SearchBar {
				id: detachedSearchBar
				anchors.fill: parent
				showMenuButton: true
				Keys.priority: Keys.AfterItem
				Keys.forwardTo: searching ? searchList : appList.viewItem
			}
		}
	}

	Item {
		id: glassPalette
		Kirigami.Theme.inherit: false
		Kirigami.Theme.colorSet: Kirigami.Theme.Window
	}
	readonly property color textColor: glassPalette.Kirigami.Theme.textColor
	readonly property string textFont: Kirigami.Theme.defaultFont.family
	readonly property real textSize: Kirigami.Theme.defaultFont.pointSize
	readonly property real appTextSize: textSize * (detachedSearch ? 1.25 : 1)
	readonly property color bgColor: Kirigami.Theme.backgroundColor
	readonly property color highlightColor: Kirigami.Theme.highlightColor
	readonly property color highlightedTextColor: Kirigami.Theme.highlightedTextColor
	readonly property bool isTop: plasmoid.location == PlasmaCore.Types.TopEdge & plasmoid.configuration.launcherPosition != 2 & !plasmoid.configuration.floating

	property bool isDarkTheme: ColorType.isDark(bgColor)
	property color contrastBgColor: isDarkTheme ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(0, 0, 0, 0.1)
	property color dimmedTextColor: Qt.rgba(textColor.r, textColor.g, textColor.b, 0.85)

	function reload() {
		searchBar.textField.clear()
		appList.reset()
	}
	function reset(){
		searchBar.textField.clear()
		appList.reset()
	}

	ColumnLayout {

		anchors.top: parent.top
		anchors.left: parent.left
		anchors.right: parent.right
		anchors.bottom: parent.bottom

		spacing: 0

		Item {
			id: inlineSearchSlot
			visible: !main.detachedSearch
			Layout.fillWidth: true
			Layout.preferredHeight: 40
			Layout.maximumHeight: Layout.preferredHeight
			Layout.rightMargin: fs.innerPadding

			SearchBar {
				id: inlineSearchBar
				anchors.fill: parent
				showMenuButton: true
				Keys.priority: Keys.AfterItem
				Keys.forwardTo: searching ? searchList : appList.viewItem
			}
		}

		Rectangle {
			visible: !main.detachedSearch
			Layout.fillWidth: true
			Layout.rightMargin: fs.innerPadding
			Layout.topMargin: 6
			Layout.bottomMargin: 6
			height: 1.5
			color: main.contrastBgColor
		}

		AllAppsList{
			id: appList
			state: "visible"
			Layout.fillHeight: true
			Layout.fillWidth: true

			Keys.priority: Keys.AfterItem
			Keys.forwardTo: searchBar.textField

			visible: opacity > 0
			states: [
				State {
					name: "visible"; when: (!searching)
					PropertyChanges { target: appList; opacity: 1.0 }
				},
				State {
					name: "hidden"; when: (searching)
					PropertyChanges { target: appList; opacity: 0.0}
				}
			]
			transitions: [
				Transition {
					to: "visible"
					PropertyAnimation {properties: 'opacity'; duration: 100; easing.type: Easing.OutQuart}
				},
				Transition {
					to: "hidden"
					PropertyAnimation {properties: 'opacity'; duration: 100; easing.type: Easing.OutQuart}
				}
			]
		}

		SearchList {
			id: searchList
			state: "hidden"
			visible: opacity > 0

			Layout.fillWidth: true
			Layout.fillHeight: true

			states: [
				State {
					name: "visible"; when: (searching)
					PropertyChanges { target: searchList; opacity: 1.0 }
				},
				State {
					name: "hidden"; when: (!searching)
					PropertyChanges { target: searchList; opacity: 0.0}
				}
			]
			transitions: [
				Transition {
					to: "visible"
					PropertyAnimation {properties: 'opacity'; duration: 100; easing.type: Easing.OutQuart}
				},
				Transition {
					to: "hidden"
					PropertyAnimation {properties: 'opacity'; duration: 100; easing.type: Easing.OutQuart}
				}
			]

			Keys.priority: Keys.AfterItem
			Keys.forwardTo: searchBar.textField
		}
	}
}
