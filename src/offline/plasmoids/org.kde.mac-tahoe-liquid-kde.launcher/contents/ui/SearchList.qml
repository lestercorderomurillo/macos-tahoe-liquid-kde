import QtQuick
import org.kde.plasma.extras as PlasmaExtras
import QtQuick.Controls
import org.kde.kirigami as Kirigami

AppListView {
	id: searchList

	Loader {
		anchors.fill: parent
		width: searchList.width - (Kirigami.Units.gridUnit * 4)

		active: searchList.count === 0
		visible: active
		asynchronous: true

		sourceComponent: PlasmaExtras.PlaceholderMessage {
			id: emptyHint

			iconName: "edit-none"
			opacity: 0
			text: i18nc("@info:status", "No matches")

			Connections {
				target: runnerModel
				function onQueryFinished() {
					showAnimation.restart()
				}
			}

			NumberAnimation {
				id: showAnimation
				duration: Kirigami.Units.longDuration
				easing.type: Easing.OutCubic
				property: "opacity"
				target: emptyHint
				to: 1
			}
		}
	}

	Connections {
		target: runnerModel
		function onQueryChanged() { 
			searchList.model = runnerModel.modelForRow(0) 
			searchList.blockingHoverFocus = true
			searchList.interceptedPosition = null
			searchList.currentIndex = 0
		}
	}
}