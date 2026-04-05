/*
    Menu — macOS-style system menu for the top panel.
    Shows system actions: About, System Settings, Sleep, Restart,
    Shut Down, Lock Screen, Log Out.

    Uses a native QMenu so the dropdown is styled by
    widgets/translucentbackground.svgz — matching the global menu bar.

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import plasma.applet.org.kde.mac.tahoe.liquid.menu

PlasmoidItem {
    id: root

    // ── About This Computer window ─────────────────────────────────
    AboutWindow { id: aboutWindow }

    readonly property string cfgIcon: Plasmoid.configuration.menuIcon || "start-here-kde-symbolic"

    Plasmoid.title: "Menu"
    Plasmoid.icon: cfgIcon
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground

    fullRepresentation: Item {}
    preferredRepresentation: compactRepresentation

    Connections {
        target: Plasmoid
        function onAboutRequested() {
            aboutWindow.show();
            aboutWindow.raise();
            aboutWindow.requestActivate();
        }
    }

    // ── compact: just the icon ──────────────────────────────────────
    // Proportions derived from macOS Tahoe menu bar:
    //   tile width  ≈ 1.75 × panel height  (e.g. 77 px at 44 px panel)
    //   icon size   ≈ 0.60 × panel height  (e.g. 26 px at 44 px panel)
    compactRepresentation: Item {
        id: compactTile

        Layout.fillHeight: true
        Layout.minimumWidth:  parent && parent.height > 0
            ? Math.round(parent.height * 2.275) - 4
            : Kirigami.Units.gridUnit * 3
        Layout.preferredWidth: Layout.minimumWidth

        // Walk up to the panel applet container so the tile can
        // extend to the full panel height (negative margins).
        readonly property var containerMargins: {
            let item = compactTile;
            while (item.parent) {
                item = item.parent;
                if (item.isAppletContainer) {
                    return item.getMargins;
                }
            }
            return undefined;
        }

        MouseArea {
            id: compactRoot
            anchors.fill: parent
            hoverEnabled: true
            onClicked: Plasmoid.trigger(compactTile)
        }

        Rectangle {
            anchors {
                fill: parent
                topMargin:    compactTile.containerMargins ? -compactTile.containerMargins('top', true) : 0
                bottomMargin: compactTile.containerMargins ? -compactTile.containerMargins('bottom', true) : 0
            }
            radius: Kirigami.Units.cornerRadius
            color: (compactRoot.containsMouse || compactRoot.containsPress)
                   ? Qt.rgba(0.5, 0.5, 0.5, 0.18) : "transparent"
        }

        Kirigami.Icon {
            anchors.centerIn: parent
            width:  Math.round(compactTile.height * 0.924) + 4
            height: Math.round(compactTile.height * 0.924) + 4
            source: root.cfgIcon
        }
    }
}
