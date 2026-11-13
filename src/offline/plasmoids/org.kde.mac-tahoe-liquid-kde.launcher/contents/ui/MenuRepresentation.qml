import QtQuick
import QtQuick.Layouts
import QtQml
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.plasmoid
import org.kde.kirigami as Kirigami

PlasmaCore.Dialog {
	id: root
	readonly property bool goldenGate: kicker.launcherPreset === 2

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

	function reposition() {
		if (!parent || !main) {
			return;
		}
		var pos = popupPosition(width, height);
		x = pos.x;
		y = pos.y;
	}

	Plasmoid.status: root.visible ? PlasmaCore.Types.RequiresAttentionStatus : PlasmaCore.Types.PassiveStatus

	readonly property int configuredIconSize: {
		switch(Plasmoid.configuration.appsIconSize){
			case 0: return Kirigami.Units.iconSizes.smallMedium;
			case 1: return Kirigami.Units.iconSizes.medium;
			case 2: return Kirigami.Units.iconSizes.large;
			case 3: return Kirigami.Units.iconSizes.huge;
			default: return 64
		}
	}
	readonly property int iconSize: Math.round(configuredIconSize * (goldenGate ? 1.3125 : (main.tahoeStyle ? 1.0625 : 1)))

	property int columns: goldenGate ? Plasmoid.configuration.goldenGateColumns : Plasmoid.configuration.numberColumns

	// Reference proportions: 7 columns, icons 60% of the column pitch,
	// and a row pitch slightly shorter than the column pitch.
	property int cellSizeHeight: goldenGate ? Math.round(configuredIconSize * 1.9375) : main.tahoeStyle ? Math.round(configuredIconSize * 1.625) : iconSize
								+ Kirigami.Units.gridUnit * 2
								+ (2 * Math.max(
												highlightItemSvg.margins.top + highlightItemSvg.margins.bottom,
												highlightItemSvg.margins.left + highlightItemSvg.margins.right
												)
								  )
	property int cellSizeWidth: goldenGate ? Math.round(configuredIconSize * 2.1875) : main.tahoeStyle ? Math.round(configuredIconSize * 1.84375) : cellSizeHeight
	property int rows: plasmoid.configuration.numberOfRows
	
	onVisibleChanged: {
		if (!visible) {
			reset();
		} else {
			reposition();
			requestActivate();
			Qt.callLater(main.focusSearch);
		}
	}

	onHeightChanged: reposition()
	onWidthChanged: reposition()

	function toggle() {
		root.visible = false;
	}

	function reset() {
		main.reset()
	}

	function popupPosition(width, height) {
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
			offset = plasmoid.configuration.floating ? parent.height * 0.35 : 0
		}
		// Fall back to bottom-left of screen area when the applet is on the desktop or floating.
		var x = offset;
		var y = screen.height - height - offset;
		var horizMidPoint = screen.x + (screen.width / 2);
		var vertMidPoint = screen.y + (screen.height / 2);
		var appletTopLeft = parent.mapToGlobal(0, 0);
		var appletBottomLeft = parent.mapToGlobal(0, parent.height);

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
						offset = (125 * 1) / 2 + parent.height * 0.125
					}
				}
				y = screen.y + parent.height + panelSvg.margins.bottom + offset;
			} else {
				if (Plasmoid.configuration.offsetY > 0) {
					offset = Plasmoid.configuration.offsetY
				}
				y = screen.y + screen.height - parent.height - height - panelSvg.margins.top - offset * 2.5;
			}
		} else {
			y = vertMidPoint - height / 2
		}

		return Qt.point(x, y + searchHeight);
	}

	FocusScope {
		id: fs
		focus: true
		implicitWidth: root.cellSizeWidth * root.columns + innerPadding * 2
			- (root.goldenGate ? dialogSvg.margins.left + dialogSvg.margins.right : 0)
		// Searchbar + separator + categories + grid
		implicitHeight: root.goldenGate
			? innerPadding * 3 + main.categoryHeight + main.gridTopSpacing + root.cellSizeHeight * rows
				- dialogSvg.margins.top - dialogSvg.margins.bottom
			: main.inlineSearchHeight + 2 + 12 + main.categoryHeight + main.gridTopSpacing + root.cellSizeHeight * rows + innerPadding - (main.tahoeStyle ? 1 : 0)
		// Dialog can write back the previous window size during a preset switch.
		// Keep the requested size independent of that feedback and constrain the
		// native window to the selected preset's dimensions.
		width: implicitWidth
		height: implicitHeight
		Layout.minimumWidth: implicitWidth
		Layout.maximumWidth: implicitWidth
		Layout.preferredWidth: implicitWidth
		Layout.minimumHeight: implicitHeight
		Layout.maximumHeight: implicitHeight
		Layout.preferredHeight: implicitHeight
		
		// We want the MainView to have an uniform margin through different plasma themes
		property real innerPadding: root.goldenGate ? root.configuredIconSize * 0.375 : 15

		Item {
			id: mainItem
			x: - dialogSvg.margins.left
			y: - dialogSvg.margins.top
			width: parent.width + dialogSvg.margins.left + dialogSvg.margins.right
			height: parent.height + dialogSvg.margins.top + dialogSvg.margins.bottom

			MainView {
				id: main
				width: mainItem.width - fs.innerPadding * (root.goldenGate ? 2 : 1)
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
