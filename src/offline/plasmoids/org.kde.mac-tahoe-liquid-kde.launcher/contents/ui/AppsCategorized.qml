import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

AppListView {
	id: appsCategorized

	showSectionSeparator: false
	highlightFollowsCurrentItem: false
	spacing: 0

	// Plain Column, not ColumnLayout: a fixed-height ColumnLayout inflates
	// the header's fillHeight spacers, pushing the grid down so the tile
	// row gets clipped at the bottom. Here every child owns its height and
	// the category is just their sum.
	delegate: Column {
		id: category

		property var currentCategory: slicedCategories[index]
		property bool expanded: false
		// Empty categories are filtered out of slicedCategories at the
		// source; this guard only covers the moment one empties live.
		property bool hasApps: grid.model && grid.model.count > 0

		width: appsCategorized.availableWidth
		height: hasApps ? implicitHeight : 0
		visible: hasApps
		clip: true
		spacing: 0

		Column {
			id: categoryHeader
			width: parent.width
			spacing: 0

			Item { width: 1; height: index > 0 ? 14 : 0 }
			Rectangle {
				id: separator
				width: parent.width
				height: 1.5
				color: index > 0 ? main.contrastBgColor : "transparent"
			}
			Item { width: 1; height: 10 }
			RowLayout {
				width: parent.width

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
			Item { width: 1; height: 10 }
		}

		GridView {
			id: grid

			leftMargin: fs.innerPadding / 2

			property var rows: {
				if (!grid.model || !grid.model.count) {
					return 0;
				}
				if(grid.model.count%root.columns == 0 )  {
					return Math.floor(grid.model.count/root.columns);
				}
				return Math.floor((grid.model.count/root.columns)+1);
			}

			property var expandedHeight: rows * root.cellSizeHeight
			property bool canMoveWithKeyboard: false

			interactive: false
			clip: true
			width: appsCategorized.availableWidth
			height: !category.hasApps ? 0
				: category.expanded ? expandedHeight : root.cellSizeHeight
			cellWidth: root.cellSizeWidth
			cellHeight: root.cellSizeHeight
			model: currentCategory.isFavorites ? globalFavorites
				: rootModel.modelForRow(currentCategory.modelIndex)

			delegate: AppGridViewDelegate {
				triggerModel: grid.model
			}

			Behavior on height {
				NumberAnimation { duration: 200 }
			}
		}
	}
}
