/*****************************************************************************
 *   Copyright (C) 2013-2014 by Eike Hein <hein@kde.org>                     *
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

import QtQuick 2.15
import QtQuick.Layouts 1.15

import org.kde.plasma.plasmoid 2.0
import org.kde.plasma.core as PlasmaCore

import org.kde.kirigami as Kirigami

Item {
    id: root

    property QtObject dashWindow: null
    readonly property bool useCustomButtonImage: (Plasmoid.configuration.useCustomButtonImage && Plasmoid.configuration.customButtonImage.length != 0)

    Kirigami.Icon {
        id: buttonIcon

        width: Plasmoid.configuration.activationIndicator ? parent.width * 0.65 : parent.width
        height: Plasmoid.configuration.activationIndicator ? parent.height * 0.65 : parent.height
        anchors.centerIn: parent

        source: useCustomButtonImage ? Plasmoid.configuration.customButtonImage : Plasmoid.configuration.icon

        active: mouseArea.containsMouse

        smooth: true

    }

    MouseArea
    {
        id: mouseArea

        anchors.fill: parent

        hoverEnabled: true

        onClicked: {
            dashWindow.visible = !dashWindow.visible;
        }
    }

    Component.onCompleted: {
        dashWindow = Qt.createQmlObject("MenuRepresentation {}", root);
        plasmoid.activated.connect(function() {
            dashWindow.visible = !dashWindow.visible;
        });
    }
}
