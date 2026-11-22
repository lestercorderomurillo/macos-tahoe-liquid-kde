// SPDX-License-Identifier: GPL-2.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Shapes

Shape {
    id: edge
    required property real radius
    readonly property real thickness: 0.75
    preferredRendererType: Shape.CurveRenderer

    function contour(inset: real): string {
        const r = Math.max(0, Math.min(radius, width / 2, height / 2) - inset);
        const right = width - inset, bottom = height - inset;
        const arc = " A" + r + " " + r + " 0 0 1 ";
        return "M" + (r + inset) + " " + inset + " H" + (right - r)
            + arc + right + " " + (inset + r) + " V" + (bottom - r)
            + arc + (right - r) + " " + bottom + " H" + (inset + r)
            + arc + inset + " " + (bottom - r) + " V" + (inset + r)
            + arc + (inset + r) + " " + inset + " Z";
    }
    ShapePath {
        strokeWidth: -1
        fillRule: ShapePath.OddEvenFill
        fillGradient: LinearGradient {
            x1: 0; y1: 0; x2: 0; y2: edge.height
            GradientStop { position: 0; color: "#968e8e8e" }
            GradientStop { position: 0.5; color: "#90808080" }
            GradientStop { position: 1; color: "#b9646464" }
        }
        PathSvg { path: edge.contour(0) + " " + edge.contour(edge.thickness) }
    }
}
