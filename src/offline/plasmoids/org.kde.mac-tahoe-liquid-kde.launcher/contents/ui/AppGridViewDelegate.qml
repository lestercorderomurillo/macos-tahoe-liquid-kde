import QtQuick 2.12
import Qt5Compat.GraphicalEffects
import org.kde.plasma.components 3.0 as PlasmaComponents
import org.kde.kirigami as Kirigami
import QtQuick.Controls 2.15

import "../code/tools.js" as Tools

Item {
	id: gridDelegate

	property var triggerModel
	readonly property var view: GridView.view

	width: root.cellSizeWidth
	height: root.cellSizeHeight

	signal itemActivated(int index, string actionId, string argument)
	signal actionTriggered(string actionId, variant actionArgument)
	signal aboutToShowActionMenu(variant actionMenu)

	property bool isDraging: false
	property bool highlighted: false

	property bool hasActionList: ((model.favoriteId !== null) || (("hasActionList" in model) && (model.hasActionList !== null)))
		

	function openActionMenu(visualParent, x, y) {
		aboutToShowActionMenu(actionMenu);
		actionMenu.visualParent = visualParent;
		actionMenu.open(x, y);
	}

	function trigger() {
		triggerModel.trigger(index, "", null);
		root.toggle()
	}

	onAboutToShowActionMenu: actionMenu => {
		const actionList = (model.hasActionList !== null) ? model.actionList : [];
		Tools.fillActionMenu(i18n, actionMenu, actionList, globalFavorites, model.favoriteId);
	}
	onActionTriggered: (actionId, actionArgument) => {
		if (Tools.triggerAction(triggerModel, model.index, actionId, actionArgument) === true) {
			kicker.expanded = false;
		}
	}

 	Kirigami.Icon {
		id: appicon
		animated: false
		y: main.detachedSearch || main.tahoeStyle ? 0 : 2 * highlightItemSvg.margins.top
		anchors.horizontalCenter: parent.horizontalCenter
		width: root.iconSize
		height: width
		source: model.decoration
	}

    // Follow the icon's alpha silhouette, including non-square third-party icons.
    // A narrow upper rim catches the light without adding a tile behind the artwork.
    InnerShadow {
        z: 1 // Render above the existing shadow effect, which also composites the source.
        anchors.fill: appicon
        visible: main.tahoeStyle
        source: appicon
        horizontalOffset: 0.5
        verticalOffset: 1
        radius: 1.5
        samples: 5
        spread: 0.35
        color: Qt.rgba(1, 1, 1, main.isDarkTheme ? 0.60 : 0.40)
        cached: true
    }

	PlasmaComponents.Label {
		id: appname
		text: ("name" in model ? model.name : model.display)
		font.family: main.textFont
		font.pointSize: main.appTextSize
		font.weight: main.detachedSearch || main.tahoeStyle ? Font.Medium : 650
		color: main.textColor
		layer.enabled: true
		layer.effect: GlassTextShadow {}
		anchors {
			top: appicon.bottom
			left: parent.left
			right: parent.right
			topMargin: Kirigami.Units.largeSpacing * (main.detachedSearch || main.tahoeStyle ? 0.5 : 1.2)
			leftMargin: Kirigami.Units.smallSpacing
			rightMargin: Kirigami.Units.smallSpacing
		}
		textFormat: Text.PlainText
		elide: main.detachedSearch || main.tahoeStyle ? Text.ElideRight : Text.ElideMiddle
		horizontalAlignment: Text.AlignHCenter
		maximumLineCount: main.detachedSearch || main.tahoeStyle ? 1 : 2
		wrapMode: main.detachedSearch || main.tahoeStyle ? Text.NoWrap : Text.Wrap
	}

	
	Rectangle {
		id: appiconHighlight

		width: parent.width - Kirigami.Units.smallSpacing * 2
		height: parent.height - Kirigami.Units.smallSpacing * 2
		radius: 22
		color: main.isDarkTheme ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(0, 0, 0, 0.12)
		border.width: 0.5
		border.color: main.isDarkTheme ? Qt.rgba(1, 1, 1, 0.15) : Qt.rgba(0, 0, 0, 0.08)

		anchors.centerIn: parent
	}

	DropShadow {
		id: appIconShadow
		visible: true
		anchors.fill: appicon
	 	// cached: true
		horizontalOffset: 0
		verticalOffset: 0
		radius: 15.0
		samples: 16
		color: "#000000"//main.glowColor1
		source: appicon

	}
	state: "default"
	states: [
		State {
			name: "highlight"; when: main.tahoeStyle ? (highlighted || (activeFocus && view.movedWithKeyboard)) : (view.canMoveWithKeyboard ? activeFocus : highlighted)
			PropertyChanges { target: appIconShadow;  color: "#4D000000"}
			PropertyChanges { target: appiconHighlight;  opacity: main.tahoeStyle ? 1 : 0.4}
		},
		State {
			name: "default"; when: main.tahoeStyle ? (!highlighted && !(activeFocus && view.movedWithKeyboard)) : (view.canMoveWithKeyboard ? !activeFocus : !highlighted)
			PropertyChanges { target: appIconShadow; color: "#33000000"}
			PropertyChanges { target: appiconHighlight;  opacity: 0}
		}
	]
	transitions: highlight
	
	MouseArea {
		id: ma
		anchors.fill: parent
		z: parent.z + 1
		acceptedButtons: Qt.LeftButton | Qt.RightButton
		cursorShape: Qt.PointingHandCursor
		hoverEnabled: !view.movedWithWheel
		onClicked: function(mouse) {
			if (mouse.button == Qt.RightButton ) {
				if (gridDelegate.hasActionList) {
					var mapped = mapToItem(gridDelegate, mouse.x, mouse.y);
					gridDelegate.openActionMenu(gridDelegate, mouse.x, mouse.y);
				}
			} else { trigger(); }
		}
		onReleased: { isDraging: false }
		onEntered: {
			// - When the movedWithKeyboard condition is broken, we do not want to
			//   select the hovered item without moving the mouse.
			// - Don't highlight separators.
			// - Don't switch category items on hover if the setting isn't enabled
			if (view.movedWithKeyboard) {
				return;
			}

			// forceActiveFocus() touches multiple items, so check for
			// activeFocus first to be more efficient.
			if (!view.activeFocus) {
				view.forceActiveFocus(Qt.MouseFocusReason);
			}
			// No need to check currentIndex first because it's
			// built into QQuickListView::setCurrentIndex() already
			view.currentIndex = index;
			highlighted = true;
		}

		onExited: { highlighted = false; }

		onPositionChanged: {
			isDraging = pressed
			if (pressed){
				if ("pluginName" in model) {
					dragHelper.startDrag(kicker, model.url, model.decoration, "text/x-plasmoidservicename", model.pluginName);
				} else {
					kicker.dragSource = gridDelegate;
					dragHelper.startDrag(kicker, model.url, model.icon);
				}
			}
		}
	}
	ActionMenu {
		id: actionMenu

		onActionClicked: {
			actionTriggered(actionId, actionArgument);
		}
	}
	Transition {
		id: highlight
		ColorAnimation {duration: 100 }
		PropertyAnimation {properties: 'opacity'; duration: 100; easing.type: Easing.OutQuart}
	}
}
