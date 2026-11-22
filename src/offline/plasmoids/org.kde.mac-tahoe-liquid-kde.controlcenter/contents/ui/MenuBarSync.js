// SPDX-License-Identifier: GPL-3.0-or-later
// One menu bar across every screen, as on macOS. Plasma builds a separate
// menu bar per screen, each with its own system tray and widgets. The
// Control Center of every bar registers here. This module is shared by every
// applet in the shell (.pragma library), like the Dock's DockSync.js. A
// setting changed in one bar, such as which tray icons are shown or hidden,
// the clock format or the Apple menu options, is copied to the matching
// widget of every other bar.
.pragma library

// Panel Colorizer stores the widget IDs of its own panel: never copy it.
var skippedPlugins = ["luisbocanegra.panel.colorizer"];
var trayPlugin = "org.kde.plasma.systemtray";
var themePrefix = "org.kde.mac-tahoe-liquid-kde.";
var stockControls = {
    wifi: "org.kde.plasma.networkmanagement",
    bluetooth: "org.kde.plasma.bluetooth",
    battery: "org.kde.plasma.battery"
};

var bars = [];

function same(a, b) {
    return JSON.stringify(a) === JSON.stringify(b);
}

function configKeys(configuration) {
    return configuration.keys().filter(function (key) {
        return !key.endsWith("Default");
    });
}

// The n-th widget of a plugin in one bar matches the n-th of the same plugin
// in another bar, so two clocks in one bar keep their own settings.
function matching(bar, plugin, occurrence) {
    var seen = 0;
    var applets = bar.containment.applets;
    for (var i = 0; i < applets.length; i++) {
        if (applets[i].pluginName !== plugin) continue;
        if (seen++ === occurrence) return applets[i];
    }
    return null;
}

function occurrenceOf(bar, applet) {
    var seen = 0;
    var applets = bar.containment.applets;
    for (var i = 0; i < applets.length; i++) {
        if (applets[i] === applet) return seen;
        if (applets[i].pluginName === applet.pluginName) seen++;
    }
    return -1;
}

function copyValue(target, key, value) {
    var configuration = target.configuration;
    if (!configuration || configuration[key] === undefined || same(configuration[key], value)) return false;
    configuration[key] = value;
    return true;
}

function prioritizeTray(bar) {
    var applets = bar.containment.applets;
    var tray = applets.find(function (applet) { return applet.pluginName === trayPlugin; });
    if (!tray?.configuration || tray.configuration.hiddenItems === undefined) return;

    var plugins = applets.map(function (applet) { return applet.pluginName; });
    var duplicates = Object.keys(stockControls).filter(function (control) {
        return plugins.indexOf(themePrefix + control) >= 0;
    }).map(function (control) { return stockControls[control]; });
    if (!duplicates.length) return;

    var shown = Array.from(tray.configuration.shownItems ?? []);
    var hidden = Array.from(tray.configuration.hiddenItems);
    var secondary = ["org.kde.plasma.clipboard", "org.kde.plasma.mediacontroller"].filter(function (id) {
        return shown.indexOf(id) < 0;
    });
    duplicates.concat(secondary).forEach(function (id) {
        if (hidden.indexOf(id) < 0) hidden.push(id);
    });
    var changed = copyValue(tray, "hiddenItems", hidden);
    changed = copyValue(tray, "shownItems", shown.filter(function (id) { return duplicates.indexOf(id) < 0; })) || changed;
    changed = copyValue(tray, "showAllItems", false) || changed;
    if (changed) tray.configuration.writeConfig();
}

function propagate(source, applet, key, value) {
    var occurrence = occurrenceOf(source, applet);
    if (occurrence < 0) return;
    for (var i = 0; i < bars.length; i++) {
        var bar = bars[i];
        if (bar === source) continue;
        var target = matching(bar, applet.pluginName, occurrence);
        if (target && copyValue(target, key, value)) target.configuration.writeConfig();
    }
}

function watch(bar, applet) {
    if (!applet || !applet.configuration || skippedPlugins.indexOf(applet.pluginName) >= 0) return;
    for (var i = 0; i < bar.watched.length; i++) if (bar.watched[i].applet === applet) return;
    var handler = function (key, value) { propagate(bar, applet, key, value); };
    applet.configuration.valueChanged.connect(handler);
    bar.watched.push({ applet: applet, handler: handler });
}

function unwatchAll(bar) {
    for (var i = 0; i < bar.watched.length; i++) {
        var entry = bar.watched[i];
        try { entry.applet.configuration.valueChanged.disconnect(entry.handler); } catch (e) {}
    }
    bar.watched = [];
}

// A new bar, for example on a screen that was just plugged in, takes the
// settings of a bar that already exists.
function adoptFrom(source, bar) {
    var applets = bar.containment.applets;
    for (var i = 0; i < applets.length; i++) {
        var applet = applets[i];
        if (!applet.configuration || skippedPlugins.indexOf(applet.pluginName) >= 0) continue;
        var original = matching(source, applet.pluginName, occurrenceOf(bar, applet));
        if (!original || !original.configuration) continue;
        var changed = false;
        var keys = configKeys(original.configuration);
        for (var k = 0; k < keys.length; k++)
            if (copyValue(applet, keys[k], original.configuration[keys[k]])) changed = true;
        if (changed) applet.configuration.writeConfig();
    }
}

function refresh(bar) {
    prioritizeTray(bar);
    var applets = bar.containment.applets;
    for (var i = 0; i < applets.length; i++) watch(bar, applets[i]);
}

function register(containment) {
    for (var i = 0; i < bars.length; i++) if (bars[i].containment === containment) return bars[i];
    var bar = { containment: containment, watched: [] };
    if (bars.length > 0) adoptFrom(bars[0], bar);
    bars.push(bar);
    refresh(bar);
    return bar;
}

function unregister(bar) {
    var index = bars.indexOf(bar);
    if (index < 0) return;
    unwatchAll(bar);
    bars.splice(index, 1);
}
