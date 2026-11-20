// SPDX-License-Identifier: GPL-3.0-or-later
.pragma library

function luminance(color) {
    function linear(value) {
        return value <= 0.04045 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4);
    }
    return 0.2126 * linear(color.r) + 0.7152 * linear(color.g) + 0.0722 * linear(color.b);
}

function ratio(a, b) {
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

function preferredText(base) {
    // Move the preferred text 40% toward its nearest luminance extreme.
    const rgb = Qt.tint(base, luminance(base) > 0.5 ? "#66ffffff" : "#66000000");
    return Qt.rgba(rgb.r, rgb.g, rgb.b, base.a);
}

function foreground(base, backdrop, surface) {
    const preferred = preferredText(base);
    if (backdrop.a === 0) return preferred;
    const background = Qt.rgba(surface.r * surface.a + backdrop.r * (1 - surface.a),
        surface.g * surface.a + backdrop.g * (1 - surface.a),
        surface.b * surface.a + backdrop.b * (1 - surface.a), 1);
    const lightness = luminance(background);
    if (ratio(luminance(preferred), lightness) >= 4.5) return preferred;
    return ratio(0, lightness) >= ratio(1, lightness) ? Qt.rgba(0,0,0,1) : Qt.rgba(1,1,1,1);
}
