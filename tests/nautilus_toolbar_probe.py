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
        button = Gtk.Button()
        content = Gtk.Box(spacing=6)
        content.append(Gtk.Image.new_from_icon_name('user-home-symbolic'))
        content.append(Gtk.Label(label='Home'))
        button.set_child(content)
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
    bar._probe_crumb = button if not query else None
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


def set_direction(widget, direction):
    widget.set_direction(direction)
    child = widget.get_first_child()
    while child:
        set_direction(child, direction)
        child = child.get_next_sibling()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--theme-variant', choices=('Light', 'Dark'),
                        help='Exercise the adaptive sheets copied from this installed theme')
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
        variant = args.theme_variant or mode
        filename = f'gtk-{mode}.css' if args.theme_variant else 'gtk.css'
        css = ROOT / f'src/offline/gtk/MacTahoeLiquidKde-{variant}/gtk-4.0/{filename}'
        provider = Gtk.CssProvider()
        errors = []
        provider.connect('parsing-error', lambda _p, _s, error: errors.append(str(error)))
        provider.load_from_data(gtk4_compatible_css(css.read_text()).encode())
        assert not errors, errors
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        for direction in (Gtk.TextDirection.LTR, Gtk.TextDirection.RTL):
            set_direction(window, direction)
            for state in ('normal', 'hover', 'active', 'checked', 'backdrop', 'disabled',
                          'backdrop-hover', 'backdrop-checked', 'checked-hover', 'disabled-checked'):
                for case, widgets in pairs:
                    files = []
                    for index, (bar, button) in enumerate(widgets):
                        flags = Gtk.StateFlags.NORMAL
                        for part in state.split('-'):
                            flags |= getattr(Gtk.StateFlags, {'normal': 'NORMAL', 'hover': 'PRELIGHT', 'active': 'ACTIVE',
                                                              'checked': 'CHECKED', 'backdrop': 'BACKDROP', 'disabled': 'INSENSITIVE'}[part])
                        button.set_state_flags(flags, True)
                        bar.set_state_flags(Gtk.StateFlags.BACKDROP if 'backdrop' in state else Gtk.StateFlags.NORMAL, True)
                        settle()
                        path = args.output / f'{len(results):03}-{mode}-{direction.value_nick}-{case}-{state}-{index}.png'
                        save(bar, path)
                        files.append(path)
                    with Image.open(files[0]) as old, Image.open(files[1]) as new:
                        assert old.size == new.size, (files, old.size, new.size)
                        assert not any(channel.getbbox() for channel in ImageChops.difference(old.convert('RGBA'), new.convert('RGBA')).split()), files
                    results.append(dict(mode=mode, direction=direction.value_nick, case=case, state=state))
        # Exercise a round trip, not just equivalence between two selectors:
        # both naming schemes can otherwise share the same rendering defect.
        for index, (bar, menu) in enumerate(pairs[0][1]):
            crumb = bar._probe_crumb
            set_direction(bar, Gtk.TextDirection.LTR)
            menu.set_state_flags(Gtk.StateFlags.NORMAL, True)
            bar.set_state_flags(Gtk.StateFlags.NORMAL, True)
            crumb.set_state_flags(Gtk.StateFlags.NORMAL, True)
            settle()
            baseline = args.output / f'{len(results):03}-{mode}-{index}-baseline.png'
            save(bar, baseline)
            with Image.open(baseline) as original:
                original = original.convert('RGBA')
                centre = original.getpixel((original.width // 2, original.height // 2))[3]
                assert centre >= (26 if mode == 'Dark' else 18), ('capsule contrast', mode, centre)
                for x, y in ((0, 0), (original.width - 1, 0),
                             (0, original.height - 1), (original.width - 1, original.height - 1)):
                    assert original.getpixel((x, y))[3] < centre / 2, ('square capsule', mode, x, y)
                for state, flags in (
                        ('checked', Gtk.StateFlags.CHECKED),
                        ('released', Gtk.StateFlags.NORMAL),
                        ('active', Gtk.StateFlags.ACTIVE),
                        ('released-again', Gtk.StateFlags.NORMAL)):
                    crumb.set_state_flags(flags, True)
                    settle()
                    frame = args.output / f'{len(results):03}-{mode}-{index}-{state}.png'
                    save(bar, frame)
                    with Image.open(frame) as image:
                        assert image.size == original.size, ('geometry changed', frame)
                        assert not any(channel.getbbox() for channel in ImageChops.difference(
                            original, image.convert('RGBA')).split()), ('current folder repainted', frame)
                    results.append(dict(mode=mode, case='path-state-roundtrip', state=state))
                bar.set_state_flags(Gtk.StateFlags.BACKDROP, True)
                settle()
                frame = args.output / f'{len(results):03}-{mode}-{index}-inactive.png'
                save(bar, frame)
                with Image.open(frame) as image:
                    assert image.size == original.size, ('inactive geometry changed', frame)
                    assert image.convert('RGBA').getpixel((image.width // 2, image.height // 2)) == original.getpixel(
                        (original.width // 2, original.height // 2)), ('inactive material changed', frame)
                results.append(dict(mode=mode, case='path-state-roundtrip', state='inactive'))
            bar.set_state_flags(Gtk.StateFlags.NORMAL, True)
            content = crumb.get_child()
            icon, label = content.get_first_child(), content.get_last_child()
            # Nautilus 46 dims ancestor labels with dim-label; Nautilus 50
            # uses dimmed. Render just the text so icon pixels cannot hide
            # an unreadable label behind a passing alpha maximum.
            icon.set_visible(False)
            settle()
            reference = args.output / f'{len(results):03}-{mode}-{index}-undimmed-label.png'
            save(crumb, reference)
            with Image.open(reference) as image:
                full_alpha = image.convert('RGBA').getchannel('A').getextrema()[1]
            assert full_alpha > 0, ('missing ancestor label', mode)
            for css_class in ('dim-label', 'dimmed'):
                label.add_css_class(css_class)
                settle()
                frame = args.output / f'{len(results):03}-{mode}-{index}-{css_class}.png'
                save(crumb, frame)
                with Image.open(frame) as image:
                    alpha = image.convert('RGBA').getchannel('A').getextrema()[1]
                    assert alpha >= full_alpha * 0.8, ('ancestor label contrast', mode, css_class, alpha, full_alpha)
                label.remove_css_class(css_class)
                results.append(dict(mode=mode, case='ancestor-label-contrast', state=css_class))
            icon.set_visible(True)

        Gtk.StyleContext.remove_provider_for_display(Gdk.Display.get_default(), provider)
    window.destroy()
    (args.output / 'result.json').write_text(json.dumps(dict(gtk=f'{Gtk.get_major_version()}.{Gtk.get_minor_version()}',
                                                          cases=results), indent=2) + '\n')
    print(f'{len(results)} matching legacy/class-based GTK toolbar renders')


if __name__ == '__main__':
    main()
