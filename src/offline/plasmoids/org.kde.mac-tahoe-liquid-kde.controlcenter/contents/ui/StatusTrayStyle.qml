// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQml.Models
import org.kde.kirigami as Kirigami

Item {
    id: style
    required property Item panelItem
    readonly property Item panelLayout: {
        for (let item = panelItem.parent; item; item = item.parent) {
            if (item instanceof GridLayout) return item;
        }
        return null;
    }

    function applet(id: string): Item {
        return panelLayout?.children.find(child => child.applet?.plasmoid?.pluginName === id)?.applet ?? null;
    }

    function findTray(item: Item): Item {
        if (!item) return null;
        if (item.visibleLayout instanceof GridView) return item;
        for (const child of item.children) {
            const tray = findTray(child);
            if (tray) return tray;
        }
        return null;
    }

    readonly property Item tray: findTray(applet("org.kde.plasma.systemtray"))
    readonly property Item arrow: tray?.visibleLayout.parent?.children.find(child => child.arrowAnimationDuration !== undefined) ?? null
    readonly property Item clock: applet("org.kde.plasma.digitalclock")

    Loader {
        active: style.clock !== null
        sourceComponent: Component {
            PanelCalendar { clock: style.clock }
        }
    }

    function delegates(grid: Item): list<Item> {
        return (grid?.contentItem.children ?? []).filter(child => child.item?.iconContainer).map(child => child.item);
    }

    // Follow Plasma's live delegates, including indicators registered after login.
    // Attach the highlight to the existing hit area and scale only the icon.
    Instantiator {
        model: style.delegates(style.tray?.visibleLayout ?? null)
               .concat(style.delegates(style.tray?.hiddenLayout ?? null))
               .concat([style.arrow, style.clock].filter(item => item !== null))
        delegate: PanelCapsule {
            id: capsule
            required property var modelData
            parent: modelData
            z: -1
            visible: hover.hovered && !modelData?.inHiddenLayout
            // The clock is exactly as wide as its text; give the capsule room around it.
            horizontalPadding: modelData === style.clock ? 6 : 0
            HoverHandler { id: hover; parent: capsule.modelData; blocking: false }

            readonly property var notifier: modelData?.model
            readonly property Item glyph: notifier?.itemType === "StatusNotifier" && !modelData.inHiddenLayout
                ? modelData.iconContainer.children.find(child => child instanceof Kirigami.Icon) ?? null : null
            Loader {
                parent: style
                active: capsule.glyph !== null
                sourceComponent: TrayArtwork { glyph: capsule.glyph }
            }
        }
    }
}
