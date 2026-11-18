// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
ControlTile {
    doubleRim: true
    materialComponent: "menus"
    cornerRadius: 20
    rimWidth: 0.75
    leftPadding: 14; rightPadding: 14
    topPadding: 12; bottomPadding: 12
    lightFallback: goldenGate ? 0.60 : 0.55
    darkFallback: goldenGate ? 0.01 : 0.48
    darkTint: goldenGate ? "white" : "black"
}
