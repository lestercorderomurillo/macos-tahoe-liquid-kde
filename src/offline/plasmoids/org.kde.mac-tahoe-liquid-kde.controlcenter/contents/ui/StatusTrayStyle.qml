// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts
import QtQml.Models
import org.kde.ksvg as KSvg
import org.kde.mac.tahoe.launcher as Native
import "ControlStyle.js" as Style
import "NotificationContrast.js" as Contrast
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

    Binding {
        target: style.tray?.visibleLayout ?? null
        property: "cellWidth"
        when: !!style.tray && !style.tray.vertical
        value: Style.panelCell
    }

    readonly property var trayWindow: {
        const window = tray?.hiddenLayout?.Window.window
        return window?.objectName === "popupWindow" ? window : null
    }
    readonly property Item trayContent: trayWindow?.mainItem ?? null
    readonly property Item nativeFrame: trayWindow?.contentItem.children.find(item => item instanceof KSvg.FrameSvgItem) ?? null
    Binding {
        target: style.trayWindow
        property: "title"
        when: !!style.trayWindow
        value: "mttkde-status-tray"
    }
    Binding {
        target: style.nativeFrame
        property: "opacity"
        when: !!style.nativeFrame
        value: 0
    }
    NotificationSurface {
        id: traySurface
        parent: style.trayWindow?.contentItem ?? null
        anchors.fill: parent
        z: -1
        visible: !!style.trayWindow
        enabled: false
    }
    Native.ControlGlass {
        id: trayGlass
        window: style.trayWindow
        surfaces: [{x: 0, y: 0, width: traySurface.width, height: traySurface.height, radius: traySurface.cornerRadius}]
    }
    Binding {
        target: style.trayContent?.Kirigami.Theme ?? null
        property: "inherit"
        when: !!style.trayContent
        value: false
    }
    Binding {
        target: style.trayContent?.Kirigami.Theme ?? null
        property: "textColor"
        when: !!style.trayContent
        value: {
            trayGlass.backdropRevision
            const center = Qt.point(traySurface.width / 2, traySurface.height / 2)
            return Contrast.foreground(style.Kirigami.Theme.textColor, trayGlass.backdropAt(center), traySurface.fillColor)
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
            HoverHandler { id: hover; parent: capsule.modelData; blocking: false }

            readonly property var notifier: modelData?.model
            readonly property bool compactIcon: notifier?.itemType === "StatusNotifier"
                && [notifier.Id, notifier.Title, notifier.ToolTipTitle, notifier.IconName].some(name => /^(?:appindicator[-_.])?(discord|slack)(?:$|[\s._-])/i.test(name ?? ""))
            readonly property Item glyph: compactIcon ? modelData.iconContainer.children.find(child => child instanceof Kirigami.Icon) ?? null : null
            Binding {
                target: capsule.glyph
                property: "scale"
                when: capsule.glyph !== null
                value: capsule.glyph ? Math.min(1, 16 / Math.max(1, capsule.glyph.width, capsule.glyph.height)) : 1
            }
        }
    }
}
