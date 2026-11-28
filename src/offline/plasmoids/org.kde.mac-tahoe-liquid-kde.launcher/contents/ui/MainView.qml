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
	readonly property QtObject iconThemeWatcher: Tahoe.IconThemeWatcher {}
	readonly property bool goldenGateEdition: false
	readonly property bool goldenGateLight: goldenGateEdition && !isDarkTheme
	property bool clipboardMode: false
    readonly property var clipboard: clipboardModel
    readonly property var clipboardList: clipboardView
    Tahoe.ClipboardModel {
        id: clipboardModel
        active: main.clipboardMode && root.visible
        onCopied: root.visible = false
    }
    function showClipboard(value) {
        clipboardMode = value;
        searchText = "";
        focusSearch();
    }
    property string searchText: ""
	readonly property bool searching: searchText !== ""
	readonly property var searchBar: detachedSearch ? detachedSearchBar : inlineSearchBar
	onSearchTextChanged: runnerModel.query = clipboardMode ? "" : searchText
	readonly property bool detachedSearch: kicker.launcherPreset === 2 && !clipboardMode
	readonly property bool tahoeStyle: !detachedSearch
	readonly property real inlineSearchHeight: 40
	readonly property real searchPopupHeight: searchPopup.height
	readonly property real searchPopupGap: Kirigami.Units.gridUnit * 0.75
	readonly property real categoryHeight: detachedSearch ? Kirigami.Units.gridUnit * 16 / 9 : (tahoeStyle ? 30 : 40)
	readonly property real gridTopSpacing: detachedSearch ? Kirigami.Units.gridUnit * 16 / 9 : (tahoeStyle ? 15 : 0)
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
	readonly property bool menuOpen: searchBar.menuOpen || clipboardView.menuOpen

	function focusSearch() {
		if (!root.visible) return;
		if (detachedSearch) {
			// Map the child only after the app panel has opened. Native parent
			// visibility changes can otherwise hide it during a rapid reopen.
			searchPopup.visible = true;
			searchPopup.activate();
		} else {
			root.requestActivate();
		}
		searchBar.textField.forceActiveFocus(Qt.PopupFocusReason);
		if (!detachedSearch) root.openingSearchFocus = false;
	}

	function closeSearchPopup() {
		searchPopup.visible = false;
	}

	onDetachedSearchChanged: {
		if (!detachedSearch) closeSearchPopup();
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
		visible: false
		onFocusWindowChanged: {
			if (focusWindow === searchPopup && root.openingSearchFocus) {
				detachedSearchBar.textField.forceActiveFocus(Qt.PopupFocusReason);
				root.openingSearchFocus = false;
			}
		}
		// PopupPlasmaWindow stays open by default. Its hideOnWindowDeactivate
		// property only exists in Plasma 6.7+; our focus group handles dismissal.
		readonly property int requestedWidth: Math.round(root.width * 0.617)
		readonly property int requestedHeight: Math.round(Kirigami.Units.iconSizes.huge * 1.625)
		function syncSize() {
			width = requestedWidth;
			height = requestedHeight;
		}
		width: requestedWidth
		height: requestedHeight
		onRequestedWidthChanged: Qt.callLater(syncSize)
		onWidthChanged: if (width !== requestedWidth) Qt.callLater(syncSize)
		onHeightChanged: if (height !== requestedHeight) Qt.callLater(syncSize)

		mainItem: FocusScope {
			id: detachedSearchSlot
			SearchBar {
				id: detachedSearchBar
                detachedWindow: true
				anchors.fill: parent
				showMenuButton: !main.clipboardMode
				Keys.priority: Keys.AfterItem
				Keys.forwardTo: clipboardMode ? clipboardView : searching ? searchList : appList.viewItem
			}
		}
	}

	Item {
		id: glassPalette
		Kirigami.Theme.inherit: false
		Kirigami.Theme.colorSet: Kirigami.Theme.Window
	}
    Tahoe.PopupBackdrop { id: appBackdrop; window: root }
    Tahoe.PopupBackdrop { id: searchBackdrop; window: searchPopup }
    Tahoe.GlassSettings { id: searchMaterial; component: "search" }
    function materialFill(settings) {
        const saved = isDarkTheme ? settings.darkOpacity : settings.lightOpacity;
        const alpha = saved >= 0 ? saved : isDarkTheme ? (goldenGateEdition ? 0.12 : 0.48) : 0.55;
        const tint = isDarkTheme ? 0 : 1;
        return Qt.rgba(tint, tint, tint, alpha);
    }
    // Compose translucent fills in premultiplied space, as Qt Quick renders them.
    function layerOver(base, top) {
        const remaining = base.a * (1 - top.a);
        const alpha = top.a + remaining;
        if (!alpha) return Qt.rgba(0, 0, 0, 0);
        return Qt.rgba((top.r * top.a + base.r * remaining) / alpha,
                       (top.g * top.a + base.g * remaining) / alpha,
                       (top.b * top.a + base.b * remaining) / alpha, alpha);
    }
    function categoryForeground(item, view, samples) {
        const profile = root.glassSettings.contrastProfiles["launcher.categories"];
        return root.glassSettings.dynamicTinting ? appBackdrop.profileGroupForeground(item, textColor,
            profile.scope === "component" ? view.visibleSamples : samples, profile) : textColor;
    }
    function categorySamples(label, view, backing) {
        if (!root.glassSettings.dynamicTinting || !root.visible) return [];
        appBackdrop.backdropRevision;
        view.contentX;
        for (let ancestor = label; ancestor; ancestor = ancestor.parent) {
            ancestor.x; ancestor.y;
        }
        const fill = materialFill(root.glassSettings);
        const center = label.mapToItem(root.contentItem, label.width / 2, label.height / 2);
        const radius = Qt.size(Math.min(label.contentWidth, label.width) * 0.4, 0);
        const clip = view.mapToItem(root.contentItem, Qt.rect(0, 0, view.width, view.height));
        return appBackdrop.categorySamples(center, radius, clip, fill,
            root.glassSettings.contrastProfiles["launcher.categories"].sampleCount, backing);
    }
    readonly property var labelProfile: root.glassSettings.contrastProfiles["launcher.label"]
    function useTextRuns(label) {
        return root.glassSettings.dynamicTinting && (labelProfile.scope === "letter"
            || (labelProfile.scope === "line" && label.wrapMode !== Text.NoWrap && label.maximumLineCount > 1));
    }
    function styledLabel(item, value, overlay = "transparent", fallback = main.textColor) {
        return Tahoe.AdaptiveContrast.styledRuns(item, value, labelProfile, r =>
            Tahoe.AdaptiveContrast.resolve(appBackdrop, item, fallback, materialFill(root.glassSettings),
                "launcher.label", item, root.contentItem, fallback, undefined, undefined, overlay, r));
    }
    function labelColor(item, sampleX = item.width / 2, overlay = "transparent", detached = false, fallback = main.textColor, textWidth = item.contentWidth, field = null) {
        if (!root.glassSettings.dynamicTinting) return fallback;
        const sampler = detached ? searchBackdrop : appBackdrop;
        const settings = detached ? searchMaterial : root.glassSettings;
        return Tahoe.AdaptiveContrast.resolve(sampler, item, fallback, materialFill(settings),
            field ? "launcher.search" : "launcher.label", field ?? item, sampler.window.contentItem, fallback, sampleX, textWidth, overlay);
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
			Layout.preferredHeight: main.inlineSearchHeight
			Layout.maximumHeight: Layout.preferredHeight
			Layout.rightMargin: fs.innerPadding

			SearchBar {
				id: inlineSearchBar
				anchors.fill: parent
				showMenuButton: !main.clipboardMode
				Keys.priority: Keys.AfterItem
				Keys.forwardTo: clipboardMode ? clipboardView : searching ? searchList : appList.viewItem
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

			visible: !main.clipboardMode && opacity > 0
			states: [
				State {
					name: "visible"; when: (!searching && !clipboardMode)
					PropertyChanges { target: appList; opacity: 1.0 }
				},
				State {
					name: "hidden"; when: (searching || clipboardMode)
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

        ClipboardView {
            id: clipboardView
            visible: main.clipboardMode
            Layout.fillWidth: true
            Layout.fillHeight: true
        }

		SearchList {
			id: searchList
			state: "hidden"
			visible: !main.clipboardMode && opacity > 0

			Layout.fillWidth: true
			Layout.fillHeight: true

			states: [
				State {
					name: "visible"; when: (searching && !clipboardMode)
					PropertyChanges { target: searchList; opacity: 1.0 }
				},
				State {
					name: "hidden"; when: (!searching || clipboardMode)
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
