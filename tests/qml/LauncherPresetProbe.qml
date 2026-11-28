import QtQuick
import LauncherInteraction 1.0
import QtQuick.Window
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.core as PlasmaCore

// Runs only in the isolated plasmoidviewer from test_launcher_presets.py.
Timer {
    id: presetProbe
    interval: 400
    running: true
    // Input helpers process nested Qt events. Re-arm after each phase returns.
    repeat: false
    property bool finished: false
    property int eventLoopDelay: 0
    property int phase: -2
    property int legacyPreset: 1
    property bool expectedGoldenGate: false
    property bool expectedDark: false
    property real inlineHeight: 0
    property real inlineWidth: 0
    property double dismissalDeadline: 0
    property Window outsideProbe: Window {
        width: 100
        height: 100
        transientParent: null
    }
    function verify(condition, label) {
        if (!condition) {
            throw new Error(label);
        }
    }
    function focusOutside() {
        outsideProbe.requestActivate();
        dismissalDeadline = Date.now() + 3000;
    }
    function awaitingDismissal() {
        // X11 delivers focus asynchronously, then the launcher runs its dismissal timer.
        if ((root.visible || searchPopup.visible) && Date.now() < dismissalDeadline) {
            --phase;
            return true;
        }
        return false;
    }
    function verifyCategoryPills() {
        const view = appList.testCategories.testView;
        verify(view.count > 0, "categories available");
        const originalX = view.contentX;
        let firstTop = null;
        let firstHeight = null;
        for (let i = 0; i < view.count; ++i) {
            view.positionViewAtIndex(i, ListView.Center);
            view.forceLayout();
            const delegate = view.itemAtIndex(i);
            verify(delegate !== null, "category delegate available: " + i);
            const label = findCategoryLabel(delegate);
            verify(label !== null, "category label available: " + i);
            const pill = label.parent;
            const alpha = expectedDark ? (pill.selected ? 0.12 : 0.06)
                : expectedGoldenGate ? (pill.selected ? 0.68 : 0.52)
                : (pill.selected ? 0.62 : 0.46);
            verify(Math.abs(pill.testBackground.color.a - alpha) < 0.005,
                   "category opacity follows edition and mode");
            const tahoe = main.tahoeStyle;
            verify(pill.testBackground.border.width === (tahoe ? 1 : 0),
                   "Tahoe glass edge follows preset 1 in either edition");
            const position = pill.mapToItem(view, 0, 0);
            verify(position.y >= 0 && position.y + pill.height <= view.height + 0.01,
                   "category pill fits its clipped viewport: " + position.y + " + " + pill.height + " <= " + view.height);
            // Qt snaps center anchors to whole logical pixels.
            verify(Math.abs(position.y + pill.height / 2 - view.height / 2) <= 0.5,
                   "category pill centered: " + label.text + " at " + position.y + " height " + pill.height + " viewport " + view.height);
            if (firstTop === null) {
                firstTop = position.y;
                firstHeight = pill.height;
            }
            verify(position.y === firstTop && pill.height === firstHeight,
                   "all category pills share their top and height: " + label.text);
        }
        view.contentX = originalX;
    }
    function findCategoryLabel(item) {
        if (item instanceof Text) return item;
        for (const child of item.children) {
            const label = findCategoryLabel(child);
            if (label) return label;
        }
        return null;
    }
    function verifyTahoeHover(item) {
        if (item.testActionMenu !== undefined) {
            item.highlighted = true;
            verify(item.state === "highlight", "Tahoe pointer entry highlights the app tile");
            item.highlighted = false;
            verify(item.state === "default", "Tahoe pointer exit clears the app tile");
            return true;
        }
        for (const child of item.children) {
            if (verifyTahoeHover(child)) return true;
        }
        return false;
    }
    function findIcon(item) {
        if (item instanceof Kirigami.Icon) {
            return item;
        }
        for (const child of item.children) {
            const icon = findIcon(child);
            if (icon) {
                return icon;
            }
        }
        return null;
    }
    function verifyPopupSize() {
        verify(Math.abs(fs.width - fs.implicitWidth) < 1 && Math.abs(fs.height - fs.implicitHeight) < 1,
               "native geometry feedback cannot retain the previous preset dimensions: " + fs.width + "/" + fs.implicitWidth);
        const buffer = LauncherInteraction.bufferSize(root);
        verify(Math.abs(buffer.width - root.width) <= 1 && Math.abs(buffer.height - root.height) <= 1,
               "rendered window buffer follows the selected preset");
        // Layouts stop sizing an invisible grid while search results are shown.
        const visibleView = main.searching ? searchList : appList.viewItem;
        verify(visibleView.width >= root.columns * root.cellSizeWidth,
               "the visible viewport fits every configured column: " + visibleView.width + "/" + (root.columns * root.cellSizeWidth));
    }
    function verifyOptionsMenu(search) {
        const button = search.testMenuButton.testButton;
        LauncherInteraction.watchMenuFrame(search.testMenuButton.testMenu);
        LauncherInteraction.click(button);
        if (eventLoopDelay > 0) {
            LauncherInteraction.pauseForEvents(eventLoopDelay);
            eventLoopDelay = 0;
        }
        let state = LauncherInteraction.menuState();
        verify(state.actions && state.actions.length === 5, "options menu includes clipboard");
        verify(state.actions[0].separator && state.actions[0].text === "View content as",
               "view heading exists in both editions");
        verify(state.actions[4].text === "Clipboard",
               "clipboard follows the view choices");
        const anchor = button.mapToGlobal(button.width, button.height);
        verify(Math.abs(state.rect.y - anchor.y) <= 2 && Math.abs(state.rect.x + state.rect.width - anchor.x) <= 2,
               "menu opens below the button aligned with its right edge: " + JSON.stringify(state.rect) + " anchor " + anchor);
        const first = LauncherInteraction.firstMenuFrame();
        verify(first.width > 0 && Math.abs(first.y - anchor.y) <= 2
               && Math.abs(first.x + first.width - anchor.x) <= 2,
               "first rendered menu frame is already aligned: " + JSON.stringify(first));
        LauncherInteraction.pointer(state.rect.x - 20, state.rect.y - 20);
        verify(LauncherInteraction.menuState().active === "", "no highlight while pointer is outside");
        const list = state.actions[2].rect;
        LauncherInteraction.pointer(state.rect.x + list.x + list.width / 2, state.rect.y + list.y + list.height / 2);
        verify(LauncherInteraction.menuState().active === "List", "pointer over List highlights List: " + JSON.stringify(state) + " / " + JSON.stringify(LauncherInteraction.menuState()));
        LauncherInteraction.pointer(state.rect.x - 20, state.rect.y - 20);
        verify(LauncherInteraction.menuState().active === "", "leaving List clears its highlight");
        LauncherInteraction.key(Qt.Key_Down);
        verify(LauncherInteraction.menuState().active === "Grid", "keyboard skips section headings");
        LauncherInteraction.key(Qt.Key_Down);
        LauncherInteraction.key(Qt.Key_Return);
        verify(plasmoid.configuration.showAllAppsInList, "menu keyboard List action works");
        LauncherInteraction.click(button);
        LauncherInteraction.key(Qt.Key_Down);
        LauncherInteraction.key(Qt.Key_Return);
        verify(!plasmoid.configuration.showAllAppsInList, "menu keyboard Grid action works");
        LauncherInteraction.click(button);
        verify(search.menuOpen, "ellipsis reopens the options");
        LauncherInteraction.click(search.textField);
        verify(root.visible && !search.menuOpen && search.textField.activeFocus,
               "textbox click: launcher " + root.visible + ", menu " + search.menuOpen + ", focus " + search.textField.activeFocus);
    }
    function verifyOptionsIcon(search) {
        const icon = findIcon(search.testMenuButton.testButton.contentItem);
        verify(icon !== null && icon.valid, "options icon loaded");
        verify(icon.Kirigami.Theme.textColor === search.textField.color, "options icon follows the search foreground");
    }
    function verifySearchContrast(search) {
        const stronger = expectedGoldenGate && (!expectedDark || main.detachedSearch);
        const tahoe = main.tahoeStyle;
        verify(search.textField.placeholderText === (tahoe ? "Applications" : "Apps"),
               "reference heading follows the selected preset");
        verify(search.testMenuButton.testButton.contentItem.opacity === (tahoe ? 0 : 1),
               "reference ellipsis replaces only the Tahoe symbol");
        verify(main.goldenGateEdition === expectedGoldenGate, "staged edition survives preset changes");
        verify(main.isDarkTheme === expectedDark, "expected appearance mode");
        verify(Math.abs(search.textField.placeholderTextColor.a - (stronger ? 1 : 0.85)) < 0.005,
               "search placeholder contrast follows edition and mode");
        const foreground = expectedGoldenGate && main.detachedSearch ? Qt.rgba(1, 1, 1, 1) : main.textColor;
        verify(search.textField.color === foreground, "search text follows its glass surface");
        verify(!search.textField.layer.enabled, "search text renders without a shadow layer");
    }
    onTriggered: {
        try {
            console.log("PROBE_PHASE", phase, root.visible, plasmoid.configuration.launcherPreset, root.width, root.height, searchPopup.width, searchPopup.height, root.active, main.popupHasFocus, searchBar.textField.activeFocus);
            console.log("PROBE_GEOMETRY", root.x, root.y, searchPopup.x, searchPopup.y);
            switch (phase++) {
            case -2:
                kicker.testAppsPin = true;
                verify(plasmoid.status === PlasmaCore.Types.HiddenStatus, "pinned Apps hides the backing applet");
                kicker.toggleDockApps(kicker.fullRepresentationItem);
                verify(root.visible, "pinned Apps opens the launcher popup");
                break;
            case -1:
                verify(plasmoid.status === PlasmaCore.Types.HiddenStatus, "opening Apps keeps the backing applet hidden");
                verify(searchBar.textField.activeFocus, "opening focuses the search input");
                verify(!main.detachedSearch || searchPopup.visible, "opening shows the capsule");
                kicker.toggleDockApps();
                verify(!root.visible, "a second activation closes the same popup");
                kicker.testAppsPin = false;
                verify(plasmoid.status === PlasmaCore.Types.PassiveStatus, "standalone Apps is visible while closed");
                break;
            case 0:
                root.title = "Launcher app role probe";
                searchPopup.title = "Launcher search role probe";
                plasmoid.configuration.launcherPreset = legacyPreset;
                plasmoid.configuration.launcherPosition = 2;
                root.visible = true;
                break;
            case 1:
                verify(root.visible, "inline panel visible");
                verify(plasmoid.status === PlasmaCore.Types.RequiresAttentionStatus, "standalone Apps remains visible while open");
                verifyPopupSize();
                verifyCategoryPills();
                if (main.tahoeStyle) {
                    verify(verifyTahoeHover(appList.viewItem), "a real Tahoe app tile was exercised");
                    verify(appList.selectedIsAllApps, "Tahoe opens the app browser");
                    verify(appList.viewItem.headerItem.favoritesView.count === root.columns,
                           "Tahoe favorites occupy one row above apps");
                    verify(appList.viewItem.contentY <= appList.viewItem.headerItem.y,
                           "Tahoe initial viewport includes its favorites row");
                    verify(root.cellSizeHeight < root.cellSizeWidth, "Tahoe uses shorter row pitch");
                    verify(appList.testCategories.testView.count === appList.slicedCategories.length,
                           "Tahoe capsules show Favorites and app categories");
                    const favorites = appList.slicedCategories[0];
                    verify(favorites.isFavorites, "Favorites is the first Tahoe capsule");
                    LauncherInteraction.click(searchBar.testMenuButton.testButton);
                    verify(searchBar.menuOpen, "options open before the category click");
                    const categoryTabs = appList.testCategories.testView;
                    categoryTabs.positionViewAtBeginning();
                    categoryTabs.forceLayout();
                    LauncherInteraction.click(categoryTabs.itemAtIndex(0));
                    verify(!searchBar.menuOpen && root.visible, "category click dismisses options");
                    verify(appList.currentModel === globalFavorites && !appList.selectedIsAllApps,
                           "Tahoe Favorites opens the full favorites model");
                    verify(appList.viewItem.count === globalFavorites.count && appList.viewItem.headerItem === null,
                           "Favorites shows every saved app without repeating the home row");
                    appList.testCategories.categorySwitched(favorites.modelIndex);
                    verify(appList.currentModel === appList.allAppsModel && appList.selectedIsAllApps,
                           "clicking Favorites again restores all apps");
                    const category = appList.slicedCategories.find(c => !c.isFavorites);
                    appList.updateShowedModel(category.modelIndex);
                    verify(appList.currentModel === category.appModel && !appList.selectedIsAllApps,
                           "Tahoe capsule filters applications");
                    appList.updateShowedModel(category.modelIndex);
                    verify(appList.currentModel === appList.allAppsModel && appList.selectedIsAllApps,
                           "clicking selected Tahoe capsule restores all apps");
                    verifyOptionsMenu(searchBar);
                }
                verify(glassPalette.Kirigami.Theme.colorSet === Kirigami.Theme.Window, "labels use the popup color set");
                verify(Qt.colorEqual(main.textColor, glassPalette.Kirigami.Theme.textColor),
                       "popup preserves the active theme's exact foreground");
                verify(!searchPopup.visible, "inline search has no second popup");
                verify(main.inlineSearchHeight === 40,
                       "Tahoe reference header preserves Golden Gate geometry");
                verify(searchBar.textField.font.pointSize === main.textSize * 2,
                       "reference search hierarchy follows preset 1");
                verify(searchBar.parent === inlineSearchSlot, "inline field parent");
                verifyOptionsIcon(searchBar);
                verifySearchContrast(searchBar);
                verify(searchBar.textField.color === main.textColor, "search and app labels share the mode foreground");
                presetProbe.inlineHeight = root.height;
                presetProbe.inlineWidth = root.width;
                // Exercise native geometry feedback before changing presets.
                root.width += 80;
                root.height += 60;
                searchBar.textField.text = "terminal";
                verify(runnerModel.query === "terminal", "search reaches runner");
                plasmoid.configuration.launcherPreset = 2;
                break;
            case 2:
                verifyPopupSize();
                verify(root.width === inlineWidth && root.height === inlineHeight, "late resize restored");
                verify(root.visible && !searchPopup.visible, "legacy preset keeps a single window");
                verify(searchBar.textField.text === "terminal", "legacy preset preserves inline query");
                searchBar.textField.clear();
                plasmoid.configuration.numberColumns = 6;
                break;
            case 3:
                verify(root.columns === 6 && root.width > inlineWidth, "configured columns resize the grid");
                verify(appList.viewItem.headerItem.favoritesView.count === 6, "favorites follow column count");
                const app = appList.viewItem.currentItem;
                verify(app !== null, "app available for its context menu");
                app.openActionMenu(app, 10, 10);
                break;
            case 4:
                verify(root.visible && appList.viewItem.currentItem.testActionMenu.opened,
                       "app context menu keeps the launcher open");
                appList.viewItem.currentItem.testActionMenu.menu.close();
                root.visible = false;
                outsideProbe.show();
                root.transientParent = outsideProbe;
                root.visible = true;
                break;
            case 5:
                verify(searchBar.textField.activeFocus, "reopened inline search takes focus");
                focusOutside();
                break;
            case 6:
                if (awaitingDismissal()) break;
                verify(!root.visible && !searchPopup.visible, "outside focus dismisses launcher");
                outsideProbe.close();
                console.log("LAUNCHER_PROBE_OK");
                finished = true;
                break;
            }
        } catch (error) {
            console.log("LAUNCHER_PROBE_FAILED", error.message);
            finished = true;
        } finally {
            if (!finished) restart();
        }
    }
}
