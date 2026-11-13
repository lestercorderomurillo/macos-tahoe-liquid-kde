import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// Runs only in the isolated plasmoidviewer from test_launcher_presets.py.
Timer {
    id: presetProbe
    interval: 400
    running: true
    repeat: true
    property int phase: -2
    property int expectedPreset: 1
    property bool expectedGoldenGate: false
    property bool expectedDark: false
    property real inlineHeight: 0
    property real inlineWidth: 0
    property size initialPopupSize
    property color originalForeground: "transparent"
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
    function verifyCapsulePosition() {
        verify(searchPopup.hideOnWindowDeactivate === undefined || !searchPopup.hideOnWindowDeactivate,
               "native popup leaves dismissal to the launcher focus group on every Plasma version");
        verify(searchPopup.y + searchPopup.height < root.y, "search above app panel");
        verify(Math.abs(searchPopup.x + searchPopup.width / 2 - root.x - root.width / 2) < 2, "capsule centered");
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
            const tahoe = !expectedGoldenGate && kicker.launcherPreset === 1;
            verify(pill.testBackground.border.width === (tahoe ? 1 : 0),
                   "Tahoe glass edge does not affect Golden Gate or preset 2");
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
    function menuAction(menu, name) {
        for (const item of menu.content) {
            if (item.objectName === name) return item;
        }
        throw new Error("missing menu action: " + name);
    }
    function verifyOptionsIcon(search) {
        const icon = findIcon(search.testMenuButton.testButton.contentItem);
        verify(icon !== null && icon.valid, "options icon loaded");
        verify(icon.Kirigami.Theme.textColor === search.textField.color, "options icon follows the search foreground");
    }
    function verifySearchContrast(search) {
        const stronger = expectedGoldenGate && !expectedDark;
        const tahoe = !expectedGoldenGate && kicker.launcherPreset === 1;
        verify(search.textField.placeholderText === (tahoe ? "Applications" : "Apps"),
               "Tahoe reference heading preserves the Golden Gate label");
        verify(search.testMenuButton.testButton.contentItem.opacity === (tahoe ? 0 : 1),
               "reference ellipsis replaces only the Tahoe symbol");
        verify(main.goldenGateEdition === expectedGoldenGate, "staged edition survives preset changes");
        verify(main.isDarkTheme === expectedDark, "expected appearance mode");
        verify(Math.abs(search.textField.placeholderTextColor.a - (stronger ? 1 : 0.85)) < 0.005,
               "search placeholder contrast follows edition and mode");
        // Instantiate the actual layer component even under CI's software renderer.
        const halo = search.textField.layer.effect.createObject(search);
        verify(halo !== null, "search halo loads");
        verify(Math.abs(halo.color.a - (stronger ? 0.65 : 0.35)) < 0.005,
               "search halo strength follows edition and mode");
        verify(halo.radius === (stronger ? 3 : 2), "search halo remains diffuse");
        halo.destroy();
    }
    onTriggered: {
        try {
            console.log("PROBE_PHASE", phase, root.visible, kicker.launcherPreset, root.width, root.height, searchPopup.width, searchPopup.height, root.active, main.popupHasFocus, searchBar.textField.activeFocus);
            console.log("PROBE_GEOMETRY", root.x, root.y, searchPopup.x, searchPopup.y);
            switch (phase++) {
            case -2:
                root.visible = true;
                break;
            case -1:
                initialPopupSize = Qt.size(root.width, root.height);
                root.visible = false;
                break;
            case 0:
                root.title = "Launcher app role probe";
                searchPopup.title = "Launcher search role probe";
                verify(kicker.launcherPreset === expectedPreset, "edition default");
                plasmoid.configuration.launcherPreset = 1;
                plasmoid.configuration.launcherPosition = 2;
                root.visible = true;
                break;
            case 1:
                verify(root.visible, "inline panel visible");
                verifyCategoryPills();
                if (!expectedGoldenGate) {
                    verify(verifyTahoeHover(appList.viewItem), "a real Tahoe app tile was exercised");
                    verify(appList.selectedIsAllApps, "Tahoe opens the app browser");
                    verify(appList.viewItem.headerItem.favoritesView.count === root.columns,
                           "Tahoe favorites occupy one row above apps");
                    verify(appList.viewItem.contentY <= appList.viewItem.headerItem.y,
                           "Tahoe initial viewport includes its favorites row");
                    verify(root.cellSizeHeight < root.cellSizeWidth, "Tahoe uses shorter row pitch");
                    verify(appList.testCategories.testView.count === appList.slicedCategories.length,
                           "Tahoe capsules show actual categories only");
                    const category = appList.slicedCategories[0];
                    appList.updateShowedModel(category.modelIndex);
                    verify(appList.currentModel === category.appModel && !appList.selectedIsAllApps,
                           "Tahoe capsule filters applications");
                    appList.updateShowedModel(category.modelIndex);
                    verify(appList.currentModel === appList.allAppsModel && appList.selectedIsAllApps,
                           "clicking selected Tahoe capsule restores all apps");
                    const options = searchBar.testMenuButton.testMenu;
                    verify(options.content[0].section && options.content[4].section,
                           "Tahoe menu separates view choices from presets");
                    options.selectedIndex = -1;
                    options.moveSelection(1);
                    verify(options.content[options.selectedIndex].objectName === "grid",
                           "keyboard navigation skips menu section labels");
                    options.moveSelection(1);
                    options.activate(options.selectedIndex);
                    verify(plasmoid.configuration.showAllAppsInList, "Tahoe List action works");
                    options.moveSelection(-1);
                    options.activate(options.selectedIndex);
                    verify(!plasmoid.configuration.showAllAppsInList, "Tahoe Grid action works");
                }
                verify(glassPalette.Kirigami.Theme.colorSet === Kirigami.Theme.Window, "labels use the popup color set");
                verify(main.textColor === glassPalette.Kirigami.Theme.textColor, "labels follow the mode-specific window foreground");
                verify(!searchPopup.visible, "inline search has no second popup");
                verify(main.inlineSearchHeight === 40,
                       "Tahoe reference header preserves Golden Gate geometry");
                verify(searchBar.textField.font.pointSize === main.textSize * (expectedGoldenGate ? 1 : 2),
                       "reference search hierarchy is scoped to Tahoe");
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
                menuAction(searchBar.testMenuButton.testMenu, "preset2").clicked();
                break;
            case 2:
                verify(root.visible && searchPopup.visible, "both detached popups visible");
                verify(root.width !== presetProbe.inlineWidth, "Golden Gate applies its own width");
                if (expectedPreset === 2) {
                    verify(root.width === initialPopupSize.width && root.height === initialPopupSize.height,
                           "Golden Gate restores its initial size after switching presets");
                }
                verify(searchBar.parent === detachedSearchSlot, "detached field parent");
                verifyOptionsIcon(searchBar);
                verifySearchContrast(searchBar);
                verify(searchBar.textField.color === main.textColor, "search and app labels share the mode foreground");
                verify(searchBar.textField.text === "terminal", "query survives preset change");
                verify(!inlineSearchSlot.visible && inlineSearchSlot.Layout.preferredHeight === 40, "detached preset hides its inline search row");
                verifyCapsulePosition();
                menuAction(searchBar.testMenuButton.testMenu, "list").clicked();
                verify(plasmoid.configuration.showAllAppsInList, "list option works");
                searchBar.testMenuButton.testMenu.openRelative();
                break;
            case 3:
                verify(root.visible && searchPopup.visible && main.menuOpen, "options menu keeps popups open");
                menuAction(searchBar.testMenuButton.testMenu, "preset1").clicked();
                searchBar.testMenuButton.testMenu.close();
                break;
            case 4:
                verify(root.visible && !searchPopup.visible, "switch back hides capsule");
                verify(searchBar.parent === inlineSearchSlot, "field returns inside panel");
                verify(root.height === presetProbe.inlineHeight, "inline height restored");
                verify(root.width === presetProbe.inlineWidth, "Tahoe applies its own width");
                verify(searchBar.textField.text === "terminal", "query survives round trip");
                plasmoid.configuration.launcherPreset = 2;
                break;
            case 5:
                outsideProbe.show();
                outsideProbe.requestActivate();
                break;
            case 6:
                verify(!root.visible && !searchPopup.visible && searchBar.textField.text === "", "outside focus closes both popups and resets query");
                outsideProbe.close();
                plasmoid.configuration.showAllAppsInList = false;
                plasmoid.configuration.showAllAppsInGrid = true;
                root.visible = true;
                break;
            case 7:
                verify(root.columns === 7, "Golden Gate starts with seven columns");
                verifyCategoryPills();
                verify(searchBar.textField.font.pointSize > main.appTextSize, "search text has its own hierarchy");
                const view = appList.viewItem;
                console.log("PROBE_CATEGORIES", JSON.stringify(appList.appsCategoriesList.map(c => ({name: c.name, modelIndex: c.modelIndex, isAllApps: c.isAllApps}))),
                            appList.selectedModelIndex, appList.selectedIsAllApps, globalFavorites.count);
                verify(view.headerItem !== null, "favorites row shown above all apps");
                verify(view.headerItem.favoritesView.count === 7, "favorites limited to one row");
                verify(view.contentY <= view.headerItem.y, "opening shows the favorites header");
                plasmoid.configuration.goldenGateColumns = 6;
                break;
            case 8:
                verify(appList.viewItem.headerItem.favoritesView.count === 6, "favorites follow the column setting");
                verifyCapsulePosition();
                root.x += 40;
                root.y += 30;
                break;
            case 9:
                verifyCapsulePosition();
                originalForeground = glassPalette.Kirigami.Theme.textColor;
                glassPalette.Kirigami.Theme.textColor = "#182838";
                break;
            case 10:
                verifyOptionsIcon(inlineSearchBar);
                verifyOptionsIcon(detachedSearchBar);
                glassPalette.Kirigami.Theme.textColor = "#e8d8c8";
                break;
            case 11:
                verifyOptionsIcon(inlineSearchBar);
                verifyOptionsIcon(detachedSearchBar);
                glassPalette.Kirigami.Theme.textColor = originalForeground;
                root.visible = false;
                // Plasma's panel/desktop can share a transient chain with the
                // launcher. QWindow.active stays true when that parent takes focus.
                outsideProbe.show();
                root.transientParent = outsideProbe;
                plasmoid.configuration.launcherPreset = 1;
                root.visible = true;
                break;
            case 12:
                verify(root.visible, "inline popup stays open with a transient parent");
                outsideProbe.requestActivate();
                break;
            case 13:
                verify(!root.visible, "focusing the parent closes the inline launcher");
                plasmoid.configuration.launcherPreset = 2;
                root.visible = true;
                break;
            case 14:
                verify(root.visible && searchPopup.visible, "detached popups reopen with a transient parent");
                root.requestActivate();
                break;
            case 15:
                verify(root.visible && searchPopup.visible, "moving focus to app panel keeps both popups open");
                main.focusSearch();
                break;
            case 16:
                verify(root.visible && searchPopup.visible, "moving focus to search keeps both popups open");
                const app = appList.viewItem.currentItem;
                verify(app !== null, "app available for its context menu");
                app.openActionMenu(app, 10, 10);
                break;
            case 17:
                verify(root.visible && searchPopup.visible && appList.viewItem.currentItem.testActionMenu.opened,
                       "app context menu keeps both popups open");
                appList.viewItem.currentItem.testActionMenu.menu.close();
                break;
            case 18:
                outsideProbe.requestActivate();
                break;
            case 19:
                verify(!root.visible && !searchPopup.visible, "focusing the parent closes both detached popups");
                console.log("LAUNCHER_PROBE_OK");
                stop();
                break;
            }
        } catch (error) {
            console.log("LAUNCHER_PROBE_FAILED", error.message);
            stop();
        }
    }
}
