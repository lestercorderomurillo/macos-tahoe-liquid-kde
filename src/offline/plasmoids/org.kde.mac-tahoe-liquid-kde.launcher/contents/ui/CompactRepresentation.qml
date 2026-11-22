import QtQuick 2.15
import QtQuick.Layouts 1.15

import org.kde.plasma.plasmoid 2.0
import org.kde.plasma.core as PlasmaCore

import org.kde.kirigami as Kirigami
import org.kde.mac.tahoe.launcher as NativeLauncher

NativeLauncher.DockIcon {
    id: root

    property QtObject dashWindow: null
    readonly property bool useCustomButtonImage: (Plasmoid.configuration.useCustomButtonImage && Plasmoid.configuration.customButtonImage.length != 0)

    NativeLauncher.IconThemeWatcher {
        onChanged: {
            root.source = "";
            root.source = Qt.binding(() => root.useCustomButtonImage
                ? Plasmoid.configuration.customButtonImage : Plasmoid.configuration.icon);
        }
    }

    inPanel: Plasmoid.formFactor === PlasmaCore.Types.Horizontal
        || Plasmoid.formFactor === PlasmaCore.Types.Vertical
    location: Plasmoid.location
    source: useCustomButtonImage ? Plasmoid.configuration.customButtonImage : Plasmoid.configuration.icon
    active: mouseArea.containsMouse
    hovered: mouseArea.containsMouse

    function activateLauncher(anchor) {
        const app = Plasmoid.configuration.launcherApplication;
        if (app && NativeLauncher.LauncherApplications.open(app)) return;
        if (!dashWindow) return;
        dashWindow.parent = anchor || root;
        dashWindow.visible = !dashWindow.visible;
    }

    MouseArea
    {
        id: mouseArea

        anchors.fill: parent

        hoverEnabled: true

        onClicked: root.activateLauncher()
    }

    Component.onCompleted: {
        dashWindow = Qt.createQmlObject("MenuRepresentation {}", root);
        plasmoid.activated.connect(root.activateLauncher);
    }
}
