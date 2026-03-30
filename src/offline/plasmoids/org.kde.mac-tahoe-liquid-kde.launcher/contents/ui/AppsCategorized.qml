import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

AppListView {
	id: appsCategorized

	showSectionSeparator: false
	highlightFollowsCurrentItem: false
	spacing: 0

	delegate: ColumnLayout {
		id: category

		property var currentCategory: slicedCategories[index]
		property bool expanded: false

		width: appsCategorized.availableWidth
		height: categoryHeader.height + root.cellSizeHeight
		clip: true
		spacing: 0

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
				visible: index > 0  // not showing on the first item
			}
			Rectangle {
                id: separator
				width: parent.width
				height: 1.5
                // not showing on the first item to avoid duplicating with searchbar separator
				color: index > 0 ? main.contrastBgColor : "transparent"
			}
			RowLayout {
				Layout.fillWidth: true

				Text {
					text:currentCategory.name
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
					text: category.expanded ? i18n("Show less") : i18n("Show more")
					visible: grid.rows > 1
					font.bold: true
					font.pixelSize: 15
					color: main.textColor
					MouseArea {
						anchors.fill: parent
						onClicked: {
						    category.expanded = !category.expanded
						}
					}
				}
			}

			/* 
			* Provides appearance of spacing between category header
			* and the start of each category grid 
			*/

			Item {
				Layout.fillWidth: true
				Layout.fillHeight: true
			}
		}


		GridView {
			id: grid

			leftMargin: fs.innerPadding / 2 // Centers the grid
			
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
			if(category.expanded) {
				category.height = grid.expandedHeight + categoryHeader.height;
			}else {
				category.height = root.cellSizeHeight + categoryHeader.height;
			}
		}
	}
}