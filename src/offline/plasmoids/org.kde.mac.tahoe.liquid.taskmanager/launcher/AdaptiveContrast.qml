// SPDX-License-Identifier: GPL-3.0-or-later
pragma Singleton
import QtQuick

QtObject {
    readonly property GlassSettings settings: GlassSettings {}
    readonly property MaterialSample layout: MaterialSample {}

    function styledRuns(item, value, profile, foregroundAt) {
        return paintRuns(item, value, profile, foregroundAt).markup;
    }

    function layoutRuns(item, value, profile) {
        const letters = profile.scope === "letter";
        const left = item.leftPadding ?? 0;
        const align = item.effectiveHorizontalAlignment ?? Qt.AlignLeft;
        const width = item.wrapMode === Text.NoWrap && align === Qt.AlignLeft
            ? 100000 : Math.max(1, item.width - left - (item.rightPadding ?? 0));
        return layout.textRuns(value, item.font, width, item.wrapMode ?? Text.NoWrap,
            align, letters);
    }

    function paintRuns(item, value, profile, foregroundAt, runs = layoutRuns(item, value, profile), scrollingContent = null) {
        const letters = profile.scope === "letter";
        const left = item.leftPadding ?? 0;
        const top = item.topPadding ?? 0;
        for (let ancestor = item; ancestor; ancestor = ancestor.parent) {
            // Launchpad refreshes at the end of a flick.
            if (ancestor !== scrollingContent) { ancestor.x; ancestor.y; }
            ancestor.rotation; ancestor.scale;
        }
        const escape = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br>");
        const lines = [];
        const colors = [];
        for (let index = 0; index < runs.length; ++index) {
            const run = runs[index];
            const r = run.bounds;
            const rect = item.mapToItem(null, r.x + left, r.y + top, r.width, r.height);
            colors.push(foregroundAt(rect, index));
            if (letters) {
                const row = run.line;
                if (!lines[row]) lines[row] = {top: run.lineTop + top, stops: []};
                lines[row].stops.push({x:r.x + r.width / 2 + left, index:index});
            }
        }
        for (const line of lines) {
            line.stops.sort((a,b) => a.x - b.x);
            const blended = layout.smoothGlyphColors(line.stops.map(s => colors[s.index]));
            for (let i = 0; i < blended.length; ++i) {
                const stop = line.stops[i];
                colors[stop.index] = blended[i];
                stop.color = blended[i].toString();
            }
        }
        let markup = "";
        for (let i = 0; i < runs.length; ++i) {
            let fragment = escape(runs[i].text);
            if (item.wrapMode === Text.NoWrap) fragment = fragment.replace(/ /g, "&#160;");
            markup += '<font color="' + colors[i].toString() + '">' + fragment + '</font>';
        }
        return {markup:markup, lines:lines};
    }

    function bounds(item, centerX, textWidth, scrollingContent = null) {
        const width = Math.min(item.width, textWidth ?? item.contentWidth ?? item.width);
        const height = Math.min(item.height, item.contentHeight ?? item.height);
        const left = item.leftPadding ?? 0;
        const right = item.rightPadding ?? 0;
        const align = item.effectiveHorizontalAlignment ?? Qt.AlignHCenter;
        const x = centerX ?? (align === Qt.AlignLeft ? left + width / 2
            : align === Qt.AlignRight ? item.width - right - width / 2 : (item.width + left - right) / 2);
        for (let parent = item; parent; parent = parent.parent) {
            if (parent !== scrollingContent) { parent.x; parent.y; }
        }
        return item.mapToItem(null, x - width / 2, (item.height - height) / 2, width, height);
    }

    function surfaceBounds(item, scrollingContent = null) {
        for (let ancestor = item; ancestor; ancestor = ancestor.parent) {
            if (ancestor !== scrollingContent) { ancestor.x; ancestor.y; }
            ancestor.scale; ancestor.rotation;
        }
        return item.mapToItem(null, 0, 0, item.width, item.height);
    }

    function resolve(sampler, item, base, fill, profileId, bubble, component, reference, centerX, textWidth, overlay = "transparent", runBounds = null, run = -1, scrollingContent = null) {
        if (!item || !sampler.window || !sampler.window.visible || !settings.dynamicTinting) return base;
        const profile = settings.contrastProfiles[profileId];
        if (!profile) return base;
        if (!scrollingContent) sampler.backdropRevision;
        const surface = profile.scope === "component" ? component : profile.scope === "bubble" ? bubble : null;
        const r = runBounds ?? (surface ? surfaceBounds(surface, scrollingContent) : bounds(item, centerX, textWidth, scrollingContent));
        const material = bubble?.contrastMaterial ?? null;
        if (material) material.revision;
        return sampler.surfaceForeground(item, r, surface ? reference : base, base, fill, profile, material, overlay, run);
    }

    function foreground(sampler, item, base, fill, centerX, textWidth) {
        return resolve(sampler, item, base, fill, "launcher.label", item, sampler.window?.contentItem, base, centerX, textWidth);
    }
}
