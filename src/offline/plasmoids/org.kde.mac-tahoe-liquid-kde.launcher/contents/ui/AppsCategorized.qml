import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

AppListView {
	id: appsCategorized

	showSectionSeparator: false
	highlightFollowsCurrentItem: false
	spacing: 0

	// Suggestions (always slicedCategories[0]) is the only category that
	// can be empty; when it is, the section below it becomes the first
	// visible one and must not draw a separator above itself.
	property bool firstCategoryEmpty: slicedCategories.length > 0
		&& rootModel.modelForRow(slicedCategories[0].modelIndex).count === 0

	delegate: ColumnLayout {
		id: category

		property var currentCategory: slicedCategories[index]
		property bool expanded: false
		property bool hasApps: grid.model.count > 0
		property bool belowVisibleCategory: index > (appsCategorized.firstCategoryEmpty ? 1 : 0)

		width: appsCategorized.availableWidth
		height: hasApps ? categoryHeader.height + root.cellSizeHeight : 0
		visible: hasApps
		clip: true
		spacing: 0

		onHasAppsChanged: updateHeight()

		ColumnLayout {
			id: categoryHeader
			width: parent.width
			spacing: 10

			/*
			* Provides appearance of spacing in the bottom of each category grid
			*/
			Item {
				Layout.fillWidth: true
				Layout.fillHeight: true
				visible: category.belowVisibleCategory
			}
			Rectangle {
                id: separator
				width: parent.width
				height: 1.5
				color: category.belowVisibleCategory ? main.contrastBgColor : "transparent"
			}
			RowLayout {
				Layout.fillWidth: true

				Text {
					text: currentCategory.name
					font.bold: true
					font.pixelSize: 15
					color: main.textColor
				}

				Item {
					Layout.fillWidth: true
					Layout.fillHeight: true
				}

				Text {
					Layout.alignment: Qt.AlignHCenter | Qt.AlignRight
					text: category.expanded ? i18n("Show Less") : i18n("Show All")
					visible: grid.rows > 1
					font.bold: false
					font.pixelSize: 12
					color: main.dimmedTextColor
					MouseArea {
						anchors.fill: parent
						onClicked: {
						    category.expanded = !category.expanded
						}
					}
				}
			}

			Item {
				Layout.fillWidth: true
				Layout.fillHeight: true
			}
		}


		GridView {
			id: grid

			leftMargin: fs.innerPadding / 2

			property var rows: {
				if(grid.model.count%root.columns == 0 )  {
					return Math.floor(grid.model.count/root.columns);
				}
				return Math.floor((grid.model.count/root.columns)+1);
			}

			property var expandedHeight: rows * root.cellSizeHeight
			property bool canMoveWithKeyboard: false

			interactive: false
			width: appsCategorized.availableWidth
			height: expandedHeight
			cellWidth: root.cellSizeWidth
			cellHeight: root.cellSizeHeight
			model: rootModel.modelForRow(currentCategory.modelIndex);

			delegate: AppGridViewDelegate {
				triggerModel: grid.model
			}
		}

		onExpandedChanged: updateHeight()

		Behavior on height {
			NumberAnimation { duration: 200 }
		}

		function updateHeight () {
			if(!category.hasApps) {
				category.height = 0;
			}else if(category.expanded) {
				category.height = grid.expandedHeight + categoryHeader.height;
			}else {
				category.height = root.cellSizeHeight + categoryHeader.height;
			}
		}
	}
}
