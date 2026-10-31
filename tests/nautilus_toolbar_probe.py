"""Opt-in GTK pixel regression for Nautilus's legacy and class-based toolbars.

Run inside a disposable desktop VM, with PyGObject/GTK4 and Pillow installed:
  python3 tests/nautilus_toolbar_probe.py --output /tmp/nautilus-toolbar
Uses real GTK widgets and the bundled stylesheet, including the older-GTK
translation. This models the upstream selector migration, not a full Nautilus
50 application qualification. No desktop settings are changed.
"""
import argparse
import ctypes
import ctypes.util
import json
from pathlib import Path
import sys
import time

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib, Gtk
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/scripts'))
from screenshot_checks import require_virtual_machine
from theme_switch import gtk4_compatible_css


def settle():
    deadline = time.monotonic() + .3
    while time.monotonic() < deadline:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.01)


def toolbar(modern, query=False):
    bar = Gtk.Box(spacing=0)
    if modern:
        bar.add_css_class('nautilus-query-editor' if query else 'nautilus-pathbar')
    else:
        bar.set_name('NautilusQueryEditor' if query else 'NautilusPathBar')
    bar.add_css_class('search' if query else 'linked')
    if query:
        entry = Gtk.Text()
        entry.set_text('Documents')
        entry.set_focusable(False)
        entry.set_hexpand(True)
        bar.append(entry)
    else:
        scroll = Gtk.ScrolledWindow(hexpand=True)
        scroll.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.NEVER)
        crumbs = Gtk.Box()
        button = Gtk.Button(label='Documents')
        button.add_css_class('current-dir')
        if modern:
            button.add_css_class('nautilus-path-button')
        else:
            button.set_name('NautilusPathButton')
        crumbs.append(button)
        scroll.set_child(crumbs)
        bar.append(scroll)
    menu = Gtk.MenuButton(icon_name='view-more-symbolic')
    menu.add_css_class('flat')
    popover = Gtk.Popover()
    popover.set_child(Gtk.Label(label='Current Folder Menu'))
    menu.set_popover(popover)
    bar.append(menu)
    return bar, menu.get_first_child()


def save(widget, destination):
    # GTK's introspection cannot marshal GskRenderNode on all supported distros.
    # Use the public C snapshot/render API for that boundary only.
    lib = ctypes.CDLL(ctypes.util.find_library('gtk-4'))
    def api(name, result, *arguments):
        fn = getattr(lib, name)
        fn.restype, fn.argtypes = result, arguments
        return fn
    pointer = ctypes.c_void_p
    paintable = api('gtk_widget_paintable_new', pointer, pointer)(hash(widget))
    snapshot = api('gtk_snapshot_new', pointer)()
    api('gdk_paintable_snapshot', None, pointer, pointer, ctypes.c_double, ctypes.c_double)(
        paintable, snapshot, widget.get_width(), widget.get_height())
    node = api('gtk_snapshot_free_to_node', pointer, pointer)(snapshot)
    assert node, 'GTK did not render the toolbar'
    renderer = widget.get_native().get_renderer()
    texture = api('gsk_renderer_render_texture', pointer, pointer, pointer, pointer)(hash(renderer), node, None)
    assert texture
    assert api('gdk_texture_save_to_png', ctypes.c_int, pointer, ctypes.c_char_p)(texture, str(destination).encode())
    api('gsk_render_node_unref', None, pointer)(node)
    gobject = ctypes.CDLL(ctypes.util.find_library('gobject-2.0'))
    gobject.g_object_unref.argtypes = [pointer]
    gobject.g_object_unref(paintable)
    gobject.g_object_unref(texture)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require_virtual_machine()
    args.output.mkdir(parents=True, exist_ok=False)
    Gtk.init()
    settings = Gtk.Settings.get_default()
    settings.set_property('gtk-enable-animations', False)
    window = Gtk.Window(title='Nautilus toolbar regression')
    container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    for margin in ('top', 'bottom', 'start', 'end'):
        getattr(container, 'set_margin_' + margin)(32)
    window.set_child(container)
    pairs = []
    for query in (False, True):
        widgets = [toolbar(modern, query) for modern in (False, True)]
        for bar, _ in widgets:
            bar.set_size_request(600, 40)
            container.append(bar)
        pairs.append(('search' if query else 'path', widgets))
    window.present()
    window.set_focus(None)
    results = []
    for mode in ('Light', 'Dark', 'Light'):
        css = ROOT / f'src/offline/gtk/MacTahoeLiquidKde-{mode}/gtk-4.0/gtk.css'
        provider = Gtk.CssProvider()
        errors = []
        provider.connect('parsing-error', lambda _p, _s, error: errors.append(str(error)))
        provider.load_from_data(gtk4_compatible_css(css.read_text()).encode())
        assert not errors, errors
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        for direction in (Gtk.TextDirection.LTR, Gtk.TextDirection.RTL):
            def set_direction(widget):
                widget.set_direction(direction)
                child = widget.get_first_child()
                while child:
                    set_direction(child)
                    child = child.get_next_sibling()
            set_direction(window)
            for state in ('normal', 'hover', 'active', 'checked', 'backdrop', 'disabled'):
                for case, widgets in pairs:
                    files = []
                    for index, (bar, button) in enumerate(widgets):
                        flags = getattr(Gtk.StateFlags, {'normal': 'NORMAL', 'hover': 'PRELIGHT', 'active': 'ACTIVE',
                                                       'checked': 'CHECKED', 'backdrop': 'BACKDROP', 'disabled': 'INSENSITIVE'}[state])
                        button.set_state_flags(flags, True)
                        bar.set_state_flags(Gtk.StateFlags.BACKDROP if state == 'backdrop' else Gtk.StateFlags.NORMAL, True)
                        settle()
                        path = args.output / f'{len(results):03}-{mode}-{direction.value_nick}-{case}-{state}-{index}.png'
                        save(bar, path)
                        files.append(path)
                    with Image.open(files[0]) as old, Image.open(files[1]) as new:
                        assert old.size == new.size, (files, old.size, new.size)
                        assert not any(channel.getbbox() for channel in ImageChops.difference(old.convert('RGBA'), new.convert('RGBA')).split()), files
                    results.append(dict(mode=mode, direction=direction.value_nick, case=case, state=state))
        Gtk.StyleContext.remove_provider_for_display(Gdk.Display.get_default(), provider)
    window.destroy()
    (args.output / 'result.json').write_text(json.dumps(dict(gtk=f'{Gtk.get_major_version()}.{Gtk.get_minor_version()}',
                                                          cases=results), indent=2) + '\n')
    print(f'{len(results)} matching legacy/class-based GTK toolbar renders')


if __name__ == '__main__':
    main()
