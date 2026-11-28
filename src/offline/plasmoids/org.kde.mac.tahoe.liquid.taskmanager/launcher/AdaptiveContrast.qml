// SPDX-License-Identifier: GPL-3.0-or-later
pragma Singleton
import QtQuick

QtObject {
    readonly property GlassSettings settings: GlassSettings {}
    function bounds(item, centerX, textWidth) {
        const width = Math.min(item.width, textWidth ?? item.contentWidth ?? item.width);
        const height = Math.min(item.height, item.contentHeight ?? item.height);
        const left = item.leftPadding ?? 0;
        const right = item.rightPadding ?? 0;
        const align = item.effectiveHorizontalAlignment ?? Qt.AlignHCenter;
        const x = centerX ?? (align === Qt.AlignLeft ? left + width / 2
            : align === Qt.AlignRight ? item.width - right - width / 2 : (item.width + left - right) / 2);
        for (let parent = item; parent; parent = parent.parent) {
            parent.x; parent.y;
        }
        return item.mapToItem(null, x - width / 2, (item.height - height) / 2, width, height);
    }

    function surfaceBounds(item) {
        for (let ancestor = item; ancestor; ancestor = ancestor.parent) {
            ancestor.x; ancestor.y; ancestor.scale; ancestor.rotation;
        }
        return item.mapToItem(null, 0, 0, item.width, item.height);
    }

    function resolve(sampler, item, base, fill, profileId, bubble, component, reference, centerX, textWidth) {
        if (!item || !sampler.window || !sampler.window.visible || !settings.dynamicTinting) return base;
        const profile = settings.contrastProfiles[profileId];
        if (!profile) return base;
        sampler.backdropRevision;
        const surface = profile.scope === "component" ? component : profile.scope === "bubble" ? bubble : null;
        const r = surface ? surfaceBounds(surface) : bounds(item, centerX, textWidth);
        const material = bubble?.contrastMaterial ?? null;
        if (material) material.revision;
        return sampler.surfaceForeground(item, r, surface ? reference : base, base, fill, profile, material);
    }

    function foreground(sampler, item, base, fill, centerX, textWidth) {
        return resolve(sampler, item, base, fill, "launcher.label", item, sampler.window?.contentItem, base, centerX, textWidth);
    }
}
