// SPDX-License-Identifier: GPL-3.0-or-later
pragma Singleton
import QtQuick

QtObject {
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

    function foreground(sampler, item, base, fill, centerX, textWidth) {
        if (!item || !sampler.window || !sampler.window.visible) return base;
        sampler.backdropRevision;
        const r = bounds(item, centerX, textWidth);
        return sampler.animatedLabelForeground(item, Qt.point(r.x + r.width / 2, r.y + r.height / 2),
            Qt.size(r.width * .4, r.height * .22), base, fill);
    }
}
