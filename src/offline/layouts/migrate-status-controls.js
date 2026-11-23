// Update themed bars in place. Keep applet instances and their settings.
(function () {
    function items(widget, key) {
        var value = widget.readConfig(key, []);
        return Array.isArray(value) ? value : String(value).split(',').filter(Boolean);
    }
    var duplicate = ['org.kde.plasma.bluetooth', 'org.kde.plasma.brightness', 'org.kde.plasma.volume'];
    var nativeNotifications = 'org.kde.plasma.notifications';
    var replaced = duplicate.concat([nativeNotifications]);
    var bars = panels();
    for (var i = 0; i < bars.length; ++i) {
        var widgets = bars[i].widgets();
        var themed = widgets.some(function (w) { return w.type === 'org.kde.mac-tahoe-liquid-kde.controlcenter'; });
        var notifications = widgets.some(function (w) { return w.type === 'org.kde.mac-tahoe-liquid-kde.notifications'; });
        var wifi = widgets.find(function (w) { return w.type === 'org.kde.mac-tahoe-liquid-kde.wifi'; });
        var glassId = 'org.kde.mac-tahoe-liquid-kde.acrylicglass';
        if (themed && wifi && !widgets.some(function (w) { return w.type === glassId; })) {
            var index = wifi.index;
            var glass = bars[i].addWidget(glassId);
            if (glass) glass.index = index;
        }
        if (themed && wifi) {
            var controls = widgets.find(function (w) { return w.type === 'org.kde.mac-tahoe-liquid-kde.controlcenter'; });
            controls.currentConfigGroup = ['General'];
            if (Number(controls.readConfig('statusOrderRevision', 0)) < 1) {
                var prefix = 'org.kde.mac-tahoe-liquid-kde.';
                var radio = widgets.find(function (w) { return w.type === prefix + 'bluetooth'; });
                if (!radio) radio = bars[i].addWidget(prefix + 'bluetooth');
                if (!radio) throw Error('Could not add the Bluetooth panel widget');
                var order = ['acrylicglass', 'notifications', 'bluetooth', 'wifi', 'battery', 'controlcenter'];
                var group = order.map(function (suffix) {
                    if (suffix === 'bluetooth') return radio;
                    return bars[i].widgets().find(function (w) { return w.type === prefix + suffix; });
                }).filter(Boolean);
                var start = Math.min.apply(null, group.filter(function (w) { return w.index >= 0; }).map(function (w) { return w.index; }));
                group.forEach(function (w, offset) { w.index = start + offset; });
            }
            if (Number(controls.readConfig('statusOrderRevision', 0)) < 2) {
                var clock = widgets.find(function (w) { return w.type === 'org.kde.plasma.digitalclock'; });
                var before = clock && bars[i].widgets().find(function (w) { return w.index === clock.index - 1; });
                if (before && (before.type === 'org.kde.plasma.marginsseparator' || before.type === controls.type)) {
                    var clockIndex = clock.index;
                    var gap = bars[i].addWidget('org.kde.plasma.panelspacer');
                    if (!gap) throw Error('Could not add the clock spacer');
                    gap.currentConfigGroup = ['General'];
                    gap.writeConfig('expanding', 'false');
                    gap.writeConfig('length', 1);
                    gap.index = clockIndex;
                }
            }
            if (Number(controls.readConfig('statusOrderRevision', 0)) < 3) {
                var themedClock = widgets.find(function (w) { return w.type === 'org.kde.plasma.digitalclock'; });
                if (themedClock) {
                    themedClock.currentConfigGroup = ['Appearance'];
                    if (themedClock.readConfig('dateFormat') === 'custom' &&
                        themedClock.readConfig('customDateFormat') === "ddd d ' | '") {
                        themedClock.writeConfig('customDateFormat', 'ddd MMM d');
                    }
                }
                controls.writeConfig('statusOrderRevision', 3);
            }
        }
        if (!themed || !notifications) continue;
        for (var j = 0; j < widgets.length; ++j) {
            var tray = widgets[j];
            if (tray.type !== 'org.kde.plasma.systemtray') continue;
            tray.currentConfigGroup = ['General'];
            tray.writeConfig('shownItems', items(tray, 'shownItems').filter(function (id) { return duplicate.indexOf(id) < 0 && id !== nativeNotifications; }));
            var hidden = items(tray, 'hiddenItems');
            duplicate.forEach(function (id) { if (hidden.indexOf(id) < 0) hidden.push(id); });
            tray.writeConfig('hiddenItems', hidden);
            // Disable the stock frontend, not the native notification service.
            var known = items(tray, 'knownItems');
            replaced.forEach(function (id) { if (known.indexOf(id) < 0) known.push(id); });
            tray.writeConfig('knownItems', known);
            tray.writeConfig('extraItems', items(tray, 'extraItems').filter(function (id) { return replaced.indexOf(id) < 0; }));
        }
    }
})();
