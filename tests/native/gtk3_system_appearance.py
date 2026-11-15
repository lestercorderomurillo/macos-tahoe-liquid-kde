"""A running GTK 3 application must follow explicitly selected theme variants."""
import json
import os
from pathlib import Path
import sys
import time
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
source = Path(sys.argv[1])
for mode in ('Light', 'Dark'):
    theme = 'MacTahoeLiquidKde-' + mode
    destination = Path.home() / '.themes' / theme
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(source / theme, target_is_directory=True)
settings = Gtk.Settings.get_default()
# This startup flag remains true even when KDE later selects the Light theme.
settings.set_property('gtk-application-prefer-dark-theme', True)
settings.set_property('gtk-theme-name', 'MacTahoeLiquidKde-Dark')
window = Gtk.Window()
label = Gtk.Label(label='Continuous system appearance')
window.add(label)
window.show_all()
results = []
for mode in ('Dark', 'Light', 'Dark', 'Light'):
    settings.set_property('gtk-theme-name', 'MacTahoeLiquidKde-' + mode)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        found, color = label.get_style_context().lookup_color('theme_bg_color')
        if found and ((color.red + color.green + color.blue) < 1.5) == (mode == 'Dark'):
            break
        time.sleep(.02)
    else:
        raise AssertionError((mode, color.to_string()))
    assert settings.get_property('gtk-application-prefer-dark-theme')
    results.append({'mode': mode, 'background': color.to_string(), 'pid': os.getpid()})
print(json.dumps(results))
window.destroy()
