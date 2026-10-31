import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.plasma.plasmoid 2.0

import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components 3.0 as PlasmaComponents

import org.kde.ksvg as KSvg

import org.kde.plasma.private.kicker 0.1 as Kicker

import org.kde.kirigami 2.20 as Kirigami

PlasmoidItem {
    id: kicker

    // Reserve a full-thickness square cell, like an icons-only task. Plasma's
    // default applet sizing otherwise caps standalone icons independently.
    Plasmoid.constraintHints: Plasmoid.CanFillArea
    Layout.fillWidth: Plasmoid.formFactor === PlasmaCore.Types.Vertical
    Layout.fillHeight: Plasmoid.formFactor === PlasmaCore.Types.Horizontal
    Layout.minimumWidth: Plasmoid.formFactor === PlasmaCore.Types.Horizontal ? height : 0
    Layout.maximumWidth: Plasmoid.formFactor === PlasmaCore.Types.Horizontal ? height : Infinity
    Layout.minimumHeight: Plasmoid.formFactor === PlasmaCore.Types.Vertical ? width : 0
    Layout.maximumHeight: Plasmoid.formFactor === PlasmaCore.Types.Vertical ? width : Infinity

    anchors.fill: parent

    signal reset

    property bool isDash: false

    readonly property int launcherPreset: Plasmoid.configuration.launcherPreset === 0
        ? Plasmoid.configuration.defaultLauncherPreset : Plasmoid.configuration.launcherPreset

    preferredRepresentation: fullRepresentation

    compactRepresentation: null
    fullRepresentation: compactRepresentation

    property Item dragSource: null

    property QtObject globalFavorites: rootModel.favoritesModel
    property QtObject systemFavorites: rootModel.systemFavoritesModel

    Plasmoid.icon: Plasmoid.configuration.useCustomButtonImage ? Plasmoid.configuration.customButtonImage : Plasmoid.configuration.icon

    function action_menuedit() {
        processRunner.runMenuEditor();
    }

    Component {
        id: compactRepresentation
        CompactRepresentation { }
    }

    Component {
        id: menuRepresentation
        MenuRepresentation { }
    }

    Kicker.RootModel {
        id: rootModel

        autoPopulate: false

        appNameFormat: 0// Plasmoid.configuration.appNameFormat
        flat: true
        sorted: true
        showSeparators: false
        appletInterface: kicker

        showAllApps: true
        showAllAppsCategorized: false
        showTopLevelItems: true//!kicker.isDash
        showRecentApps: true
        showRecentDocs: false
        showPowerSession: false
       // showRecentContacts: true//Plasmoid.configuration.showRecentContacts
       // recentOrdering: 1 // Plasmoid.configuration.recentOrdering

        onRecentOrderingChanged: {
            Plasmoid.configuration.recentOrdering = recentOrdering;
        }

        Component.onCompleted: {
            favoritesModel.initForClient("org.kde.plasma.kicker.favorites.instance-" + Plasmoid.id)

           // kicker.logListModel("rootmodel", rootModel);
            if (!Plasmoid.configuration.favoritesPortedToKAstats) {
                if (favoritesModel.count < 1) {
                    favoritesModel.portOldFavorites(Plasmoid.configuration.favoriteApps);
                }
                Plasmoid.configuration.favoritesPortedToKAstats = true;
            }
        }
    }

    Connections {
        target: globalFavorites

        function onFavoritesChanged() {
            Plasmoid.configuration.favoriteApps = target.favorites;
        }
    }

    Connections {
        target: systemFavorites

        function onFavoritesChanged() {
            Plasmoid.configuration.favoriteSystemActions = target.favorites;
        }
    }

    Connections {
        target: Plasmoid.configuration

        function onFavoriteAppsChanged() {
            globalFavorites.favorites = Plasmoid.configuration.favoriteApps;
        }

        function onFavoriteSystemActionsChanged() {
            systemFavorites.favorites = Plasmoid.configuration.favoriteSystemActions;
        }
    }

    Kicker.RunnerModel {
        id: runnerModel

        favoritesModel: globalFavorites
        appletInterface: kicker
        mergeResults: true
    }

    Kicker.DragHelper {
        id: dragHelper

        dragIconSize: Kirigami.Units.iconSizes.medium
    }

    Kicker.ProcessRunner {
        id: processRunner;
    }

    KSvg.FrameSvgItem {
        id: highlightItemSvg

        visible: false

        imagePath: "widgets/viewitem"
        prefix: "hover"
    }

    KSvg.FrameSvgItem {
        id: panelSvg
        visible: false
        imagePath: "widgets/panel-background"
    }

    KSvg.FrameSvgItem {
        id: dialogSvg
        visible: false
        imagePath: "dialogs/background"
    }

    PlasmaComponents.Label {
        id: toolTipDelegate

        width: contentWidth
        height: contentHeight

        property Item toolTip

        text: (toolTip != null) ? toolTip.text : ""
    }

    function resetDragSource() {
        dragSource = null;
    }

     Plasmoid.contextualActions: [
        PlasmaCore.Action {
            text: i18n("Edit Applications…")
            icon.name: "kmenuedit"
            visible: Plasmoid.immutability !== PlasmaCore.Types.SystemImmutable
            onTriggered: processRunner.runMenuEditor()
        }
    ]

    Component.onCompleted: {
        //plasmoid.setAction("menuedit", i18n("Edit Applications..."));
        rootModel.refreshed.connect(reset);

        dragHelper.dropped.connect(resetDragSource);
    }
}
