#!/usr/bin/env python3
"""Keep a real GTK window alive while the VM changes its desktop appearance."""
import argparse
import json
from pathlib import Path
import gi

parser = argparse.ArgumentParser()
parser.add_argument('--gtk', choices=('3', '4'), required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if Path('/sys/class/dmi/id/product_name').read_text().strip() != 'MTTKDE release capture':
    raise SystemExit('This probe requires the disposable capture VM')
gi.require_version('Gtk', args.gtk + '.0')
from gi.repository import Gtk, GLib
if args.gtk == '4':
    gi.require_version('Adw', '1')
    from gi.repository import Adw
    app = Adw.Application(application_id='org.mttkde.AppearanceGtk4')
else:
    app = Gtk.Application(application_id='org.mttkde.AppearanceGtk3')

def activate(app):
    window = Gtk.ApplicationWindow(application=app, title='GTK ' + args.gtk + ' appearance')
    window.set_default_size(380, 180)
    label = Gtk.Label(label='This window stays open during every transition')
    if args.gtk == '4':
        window.set_child(label)
    else:
        window.add(label)
        window.show_all()
    window.present()
    def snapshot():
        context = label.get_style_context()
        def color(name):
            found, value = context.lookup_color(name)
            return [value.red, value.green, value.blue, value.alpha] if found else None
        result = {'gtk': args.gtk, 'background': color('window_bg_color' if args.gtk == '4' else 'theme_bg_color'),
                  'foreground': color('window_fg_color' if args.gtk == '4' else 'theme_fg_color'),
                  'theme': Gtk.Settings.get_default().get_property('gtk-theme-name')}
        if args.gtk == '4':
            result['dark'] = Adw.StyleManager.get_default().get_dark()
        temporary = args.output.with_suffix('.tmp')
        temporary.write_text(json.dumps(result))
        temporary.replace(args.output)
        return True
    GLib.timeout_add(250, snapshot)
app.connect('activate', activate)
app.run([])
