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
