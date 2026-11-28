import QtQuick
import org.kde.mac.tahoe.launcher as NativeGlass
import QtQml
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.plasmoid
import org.kde.kirigami as Kirigami

PlasmaCore.Dialog {
	id: root
	title: "mttkde-apps"
	property Item dockAnchor
	readonly property NativeGlass.GlassSettings glassSettings: NativeGlass.GlassSettings {
		component: "apps"
		window: root
		frameSource: main.goldenGateEdition && !main.clipboardMode ? "dialogs/launcher-apps" : ""
	}

	objectName: "popupWindow"
	type: PlasmaCore.Dialog.AppletPopup
	flags: Qt.WindowStaysOnTopHint

	location: Plasmoid.configuration.floating || Plasmoid.configuration.launcherPosition == 2 ? "Floating" : Plasmoid.location
	hideOnWindowDeactivate: false

	function checkDismissal() {
		if (visible) {
			dismissTimer.restart();
		}
	}

	readonly property Timer dismissTimer: Timer {
		// Focus can pass between the app panel, search capsule and options menu.
		interval: 150
		onTriggered: {
			if (root.visible && !main.popupHasFocus && !main.menuOpen) {
				root.visible = false;
			}
		}
	}

	function syncSize() {
		// Dialog writes compositor geometry back into mainItem. Apply the
		// requested size after the preset bindings have settled.
		width = Math.round(fs.implicitWidth + margins.left + margins.right);
		height = Math.round(fs.implicitHeight + margins.top + margins.bottom);
		fs.width = fs.implicitWidth;
		fs.height = fs.implicitHeight;
		reposition();
	}

	function reposition() {
		if (!parent || !main) {
			return;
		}
		var pos = popupPosition(width, height);
		x = pos.x;
		y = pos.y;
	}

	readonly property int configuredIconSize: {
		switch(Plasmoid.configuration.appsIconSize){
			case 0: return Kirigami.Units.iconSizes.smallMedium;
			case 1: return Kirigami.Units.iconSizes.medium;
			case 2: return Kirigami.Units.iconSizes.large;
			case 3: return Kirigami.Units.iconSizes.huge;
			default: return 64
		}
	}
	readonly property int iconSize: Math.round(configuredIconSize * 1.0625)
	readonly property int columns: Plasmoid.configuration.numberColumns
	// At 150% scale the reference column and row pitches are 171 and 151 pixels.
	readonly property int cellSizeWidth: Math.round(configuredIconSize * 114 / 64)
	readonly property int cellSizeHeight: Math.round(configuredIconSize * 101 / 64)
	property int rows: plasmoid.configuration.numberOfRows
	
	property bool openingSearchFocus: false
	onActiveChanged: {
		if (active && openingSearchFocus) Qt.callLater(main.focusSearch);
	}
	onVisibleChanged: {
		openingSearchFocus = visible;
		if (!visible) {
			main.closeSearchPopup();
			reset();
		} else {
			syncSize();
			requestActivate();
			Qt.callLater(main.focusSearch);
		}
	}

	onHeightChanged: {
		reposition();
		if (height !== Math.round(fs.implicitHeight + margins.top + margins.bottom)) Qt.callLater(syncSize);
	}
	onWidthChanged: {
		reposition();
		if (width !== Math.round(fs.implicitWidth + margins.left + margins.right)) Qt.callLater(syncSize);
	}

	function toggle() {
		root.visible = false;
	}

	function reset() {
		main.reset()
	}

	function popupPosition(width, height) {
		const anchor = dockAnchor || parent;
		var searchHeight = main.detachedSearch ? main.searchPopupHeight + main.searchPopupGap : 0;
		height += searchHeight;
		var screenAvail = Plasmoid.availableScreenRect;
		var screen/*Geom*/ = kicker.screenGeometry;
		//QtBug - QTBUG-64115
		/*var screen = Qt.rect(screenAvail.x + screenGeom.x,
				screenAvail.y + screenGeom.y,
				screenAvail.width,
				screenAvail.height);*/

		var offset = 0

		if (Plasmoid.configuration.offsetX > 0 && Plasmoid.configuration.floating) {
			offset = Plasmoid.configuration.offsetX
		} else {
			offset = plasmoid.configuration.floating ? anchor.height * 0.35 : 0
		}
		// Fall back to bottom-left of screen area when the applet is on the desktop or floating.
		var x = offset;
		var y = screen.height - height - offset;
		var horizMidPoint = screen.x + (screen.width / 2);
		var vertMidPoint = screen.y + (screen.height / 2);
		var appletTopLeft = anchor.mapToGlobal(0, 0);
		var appletBottomLeft = anchor.mapToGlobal(0, anchor.height);

		if (Plasmoid.configuration.launcherPosition != 0){
			x = horizMidPoint - width / 2;
		} else {
			x = (appletTopLeft.x < horizMidPoint) ? screen.x : (screen.x + screen.width) - width;
			if (Plasmoid.configuration.floating) {
				if (appletTopLeft.x < horizMidPoint) {
					x += offset
				} else if (appletTopLeft.x + width > horizMidPoint){
					x -= offset
				}
			}
		}

		if (Plasmoid.configuration.launcherPosition != 2){
			if (Plasmoid.location == PlasmaCore.Types.TopEdge) {
				if (Plasmoid.configuration.floating) {
											/*this is floatingAvatar.width*/
					if (Plasmoid.configuration.offsetY > 0) {
						offset = (125 * 1) / 2 + Plasmoid.configuration.offsetY
					} else {
						offset = (125 * 1) / 2 + anchor.height * 0.125
					}
				}
				y = screen.y + anchor.height + panelSvg.margins.bottom + offset;
			} else {
				if (Plasmoid.configuration.offsetY > 0) {
					offset = Plasmoid.configuration.offsetY
				}
				y = screen.y + screen.height - anchor.height - height - panelSvg.margins.top - offset * 2.5;
			}
		} else {
			y = vertMidPoint - height / 2
		}

		return Qt.point(x, y + searchHeight);
	}

	FocusScope {
		id: fs
		focus: true
		// The reference frame is 615 × 526 logical pixels at the default 5 × 4 grid.
		implicitWidth: main.clipboardMode ? Math.round(main.textSize * 60)
			: root.cellSizeWidth * root.columns + 45 - root.margins.left - root.margins.right
		implicitHeight: main.clipboardMode
			? Math.round(main.inlineSearchHeight + 18 + Math.max(2, Math.min(6, main.clipboardList.entries.length)) * main.textSize * 5.2)
			: main.inlineSearchHeight + main.categoryHeight + main.gridTopSpacing
				+ root.cellSizeHeight * root.rows + 37 - root.margins.top - root.margins.bottom
		// Let Dialog follow the content size. Equal, changing min/max hints
		// can leave Wayland constrained to the previous preset's configure.
		width: implicitWidth
		height: implicitHeight
		onWidthChanged: if (width !== implicitWidth) Qt.callLater(root.syncSize)
		onHeightChanged: if (height !== implicitHeight) Qt.callLater(root.syncSize)
		onImplicitWidthChanged: Qt.callLater(root.syncSize)
		onImplicitHeightChanged: Qt.callLater(root.syncSize)
		Component.onCompleted: Qt.callLater(root.syncSize)
		
		// We want the MainView to have an uniform margin through different plasma themes
		property real innerPadding: 15

		Item {
			id: mainItem
			x: - dialogSvg.margins.left
			y: - dialogSvg.margins.top
			width: parent.width + dialogSvg.margins.left + dialogSvg.margins.right
			height: parent.height + dialogSvg.margins.top + dialogSvg.margins.bottom

			MainView {
				id: main
				width: mainItem.width - fs.innerPadding
				height: mainItem.height - fs.innerPadding * (main.tahoeStyle ? 1 : 2)
				x: fs.innerPadding
				y: main.tahoeStyle ? 8 : fs.innerPadding
			}
		}

		Keys.onPressed: function(event) {
			if (event.key == Qt.Key_Escape) {
				root.visible = false;
			}
		}
	}

	function refreshModel() {
		main.reload()
	}

	Component.onCompleted: {
		kicker.reset.connect(reset);
		rootModel.refresh();
	}
}
