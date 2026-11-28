// SPDX-License-Identifier: GPL-3.0-or-later
pragma Singleton
import QtQuick

QtObject {
    readonly property GlassSettings settings: GlassSettings {}
    readonly property MaterialSample layout: MaterialSample {}

    function styledRuns(item, value, profile, foregroundAt) {
        const letters = profile.scope === "letter";
        const left = item.leftPadding ?? 0;
        const top = item.topPadding ?? 0;
        const align = item.effectiveHorizontalAlignment ?? Qt.AlignLeft;
        const width = item.wrapMode === Text.NoWrap && align === Qt.AlignLeft
            ? 100000 : Math.max(1, item.width - left - (item.rightPadding ?? 0));
        const runs = layout.textRuns(value, item.font, width, item.wrapMode ?? Text.NoWrap,
            align, letters);
        for (let ancestor = item; ancestor; ancestor = ancestor.parent) {
            ancestor.x; ancestor.y; ancestor.rotation; ancestor.scale;
        }
        const escape = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br>");
        let result = "";
        for (let index = 0; index < runs.length; ++index) {
            const run = runs[index];
            const r = run.bounds;
            const rect = item.mapToItem(null, r.x + left, r.y + top, r.width, r.height);
            const color = foregroundAt(rect, index);
            result += '<font color="' + color.toString() + '">' + escape(run.text) + '</font>';
        }
        return result;
    }

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

    function resolve(sampler, item, base, fill, profileId, bubble, component, reference, centerX, textWidth, overlay = "transparent", runBounds = null, run = -1) {
        if (!item || !sampler.window || !sampler.window.visible || !settings.dynamicTinting) return base;
        const profile = settings.contrastProfiles[profileId];
        if (!profile) return base;
        sampler.backdropRevision;
        const surface = profile.scope === "component" ? component : profile.scope === "bubble" ? bubble : null;
        const r = runBounds ?? (surface ? surfaceBounds(surface) : bounds(item, centerX, textWidth));
        const material = bubble?.contrastMaterial ?? null;
        if (material) material.revision;
        return sampler.surfaceForeground(item, r, surface ? reference : base, base, fill, profile, material, overlay, run);
    }

    function foreground(sampler, item, base, fill, centerX, textWidth) {
        return resolve(sampler, item, base, fill, "launcher.label", item, sampler.window?.contentItem, base, centerX, textWidth);
    }
}
