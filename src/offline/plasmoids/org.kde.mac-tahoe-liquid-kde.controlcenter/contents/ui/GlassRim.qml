// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
// The Dock's opposing light rims, redrawn for each control's own radius.
// This is only the edge; the compositor supplies the real backdrop blur.
Canvas {
    id: rim
    property real cornerRadius: 24
    property bool lightMode: true
    antialiasing: true
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onCornerRadiusChanged: requestPaint()
    onLightModeChanged: requestPaint()
    onPaint: {
        const ctx = getContext("2d"); ctx.reset();
        const inset = 0.65, w = width - 2 * inset, h = height - 2 * inset;
        if (w <= 0 || h <= 0) return;
        const r = Math.max(0, Math.min(cornerRadius - inset, w / 2, h / 2));
        const x = inset, y = inset;
        ctx.beginPath(); ctx.moveTo(x+r,y); ctx.lineTo(x+w-r,y);
        ctx.arcTo(x+w,y,x+w,y+r,r); ctx.lineTo(x+w,y+h-r);
        ctx.arcTo(x+w,y+h,x+w-r,y+h,r); ctx.lineTo(x+r,y+h);
        ctx.arcTo(x,y+h,x,y+h-r,r); ctx.lineTo(x,y+r);
        ctx.arcTo(x,y,x+r,y,r); ctx.closePath();
        const edge = ctx.createLinearGradient(0,0,width*0.3,height);
        edge.addColorStop(0, lightMode ? "rgba(255,255,255,0.82)" : "rgba(255,255,255,0.5)");
        edge.addColorStop(0.45,"rgba(255,255,255,0.08)");
        edge.addColorStop(0.72,"rgba(0,0,0,0.12)");
        edge.addColorStop(1,"rgba(255,255,255,0.34)");
        ctx.strokeStyle = edge; ctx.lineWidth = 1.25; ctx.stroke();
    }
}
