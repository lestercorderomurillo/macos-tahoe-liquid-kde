// Update only themed bars. Preserve applet order, geometry and app status icons.
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
