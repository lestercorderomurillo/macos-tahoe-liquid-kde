/*****************************************************************************
 *   Copyright (C) 2014 by Weng Xuetian <wengxt@gmail.com>                   *
 *   Copyright (C) 2013-2017 by Eike Hein <hein@kde.org>                     *
 *   Copyright (C) 2021 by Prateek SU <pankajsunal123@gmail.com>             *
 *   Copyright (C) 2022 by Friedrich Schriewer <friedrich.schriewer@gmx.net> *
 *                                                                           *
 *   This program is free software; you can redistribute it and/or modify    *
 *   it under the terms of the GNU General Public License as published by    *
 *   the Free Software Foundation; either version 2 of the License, or       *
 *   (at your option) any later version.                                     *
 *                                                                           *
 *   This program is distributed in the hope that it will be useful,         *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of          *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the           *
 *   GNU General Public License for more details.                            *
 *                                                                           *
 *   You should have received a copy of the GNU General Public License       *
 *   along with this program; if not, write to the                           *
 *   Free Software Foundation, Inc.,                                         *
 *   51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA .          *
 ****************************************************************************/

import QtQuick
import QtQuick.Layouts
import QtQml
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.plasmoid
import org.kde.kirigami as Kirigami

PlasmaCore.Dialog {
	id: root

	objectName: "popupWindow"
	flags: Qt.WindowStaysOnTopHint

	location: Plasmoid.configuration.floating || Plasmoid.configuration.launcherPosition == 2 ? "Floating" : Plasmoid.location
	hideOnWindowDeactivate: true

	Plasmoid.status: root.visible ? PlasmaCore.Types.RequiresAttentionStatus : PlasmaCore.Types.PassiveStatus

	property int iconSize: { 
		switch(Plasmoid.configuration.appsIconSize){
			case 0: return Kirigami.Units.iconSizes.smallMedium;
			case 1: return Kirigami.Units.iconSizes.medium;
			case 2: return Kirigami.Units.iconSizes.large;
			case 3: return Kirigami.Units.iconSizes.huge;
			default: return 64
		}
	}

	property int columns: Plasmoid.configuration.numberColumns

	property int cellSizeHeight: iconSize
								+ Kirigami.Units.gridUnit * 2
								+ (2 * Math.max(
												highlightItemSvg.margins.top + highlightItemSvg.margins.bottom,
												highlightItemSvg.margins.left + highlightItemSvg.margins.right
												)
								  )
	property int cellSizeWidth: cellSizeHeight //+ Kirigami.Units.gridUnit
	property int rows: plasmoid.configuration.numberOfRows
	
	onVisibleChanged: {
		if (!visible) {
			reset();
		} else {
			var pos = popupPosition(width, height);
			x = pos.x;
			y = pos.y;
			requestActivate();
		}
	}

	onHeightChanged: {
		var pos = popupPosition(width, height);
		x = pos.x;
		y = pos.y;
	}

	onWidthChanged: {
		var pos = popupPosition(width, height);
		x = pos.x;
		y = pos.y;
	}

	function toggle() {
		root.visible = false;
	}

	function reset() {
		main.reset()
	}

	function popupPosition(width, height) {
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

		return Qt.point(x, y);
	}

	FocusScope {
		id: fs
		focus: true
		width:  (root.cellSizeWidth * Plasmoid.configuration.numberColumns)+ innerPadding*2//Kirigami.Units.gridUnit*2
		// Searchbar.height + separator.height  + categories switcher.height 
		height: 40 + 2 + 40 + (root.cellSizeHeight *rows) + innerPadding//550 * 1
		
		
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
				width:  mainItem.width - (fs.innerPadding)
				height: mainItem.height - (fs.innerPadding*2)
				x: fs.innerPadding
				y: fs.innerPadding
			}
		}

		Keys.onPressed: {
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
