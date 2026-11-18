"""Reject the mixed light desktop/dark Files capture, even with matching settings."""
import pytest

import screenshot_checks as checks


@pytest.mark.parametrize('mode', ['light', 'dark'])
def test_files_pixels_reject_opposite_mode(mode):
    Image = pytest.importorskip('PIL.Image')
    windows = [{'resourceClass': 'org.gnome.Nautilus', 'caption': 'Documents',
                'geometry': {'x': 20, 'y': 30, 'width': 300, 'height': 200}}]
    expected = Image.new('RGB', (640, 480), 'white' if mode == 'light' else '#242424')
    assert checks.check_files_pixels(expected, mode, windows, 1)['matching_fraction'] == 1
    with pytest.raises(checks.AppearanceMismatch, match='pixels contradict'):
        checks.check_files_pixels(expected, 'dark' if mode == 'light' else 'light', windows, 1)
    with pytest.raises(checks.AppearanceMismatch, match='Documents window'):
        checks.check_files_pixels(expected, mode, [], 1)
    with pytest.raises(checks.AppearanceMismatch, match='outside'):
        checks.check_files_pixels(expected, mode, windows, 4)


@pytest.mark.parametrize('mode', ['light', 'dark'])
def test_session_rejects_stale_css_when_settings_all_match(tmp_path, monkeypatch, mode):
    theme = 'MacTahoeLiquidKde-' + mode.capitalize()
    def read(*args):
        if 'kwinrc' in args:
            from theme_switch import decoration_theme
            return '__aurorae__svg__' + decoration_theme(mode)
        if args[0] == 'gsettings':
            return repr('prefer-' + mode if args[-1] == 'color-scheme' else theme)
        if 'ColorScheme' in args:
            return theme.replace('Kde-', 'Kde')
        if 'Kvantum/kvantum.kvconfig' in args:
            return 'mac-tahoe-liquid-kde' + ('Dark' if mode == 'dark' else '')
        return theme
    monkeypatch.setattr(checks, '_read', read)
    for version in ('3.0', '4.0'):
        path = tmp_path / f'.config/gtk-{version}'
        path.mkdir(parents=True)
        (path / 'settings.ini').write_text('[Settings]\ngtk-theme-name=' + theme +
            '\ngtk-application-prefer-dark-theme=' + str(mode == 'dark').lower())
    source = tmp_path / '.themes' / theme / 'gtk-4.0/gtk.css'
    source.parent.mkdir(parents=True)
    source.write_text('window { color: black; }')
    active = tmp_path / '.config/gtk-4.0/gtk.css'
    active.write_text('window { color: white; }')
    with pytest.raises(checks.AppearanceMismatch, match='stale or custom CSS'):
        checks.check_session(mode, home=tmp_path)
    active.write_text(source.read_text() + "\n@import 'colors.css';")
    assert checks.check_session(mode, home=tmp_path)['GTK 4 stylesheet'] == theme

    from theme_switch import GTK4_ADAPTIVE_CSS

    active.write_text(GTK4_ADAPTIVE_CSS)
    variant = f'gtk-{mode.capitalize()}.css'
    packaged_variant = source.with_name(variant)
    imported_variant = active.with_name(variant)
    packaged_variant.write_text('/* adaptive variant */\n' + source.read_text())
    imported_variant.write_text(source.read_text())
    with pytest.raises(checks.AppearanceMismatch, match='adaptive sheet imports stale'):
        checks.check_session(mode, home=tmp_path)
    imported_variant.write_text(packaged_variant.read_text())
    assert checks.check_session(mode, home=tmp_path)['GTK 4 stylesheet'] == theme


def test_wait_requires_consecutive_matches(monkeypatch):
    outcomes = iter([{}, checks.AppearanceMismatch('stale'), {}, {}, {}])
    observed = []
    def check(mode):
        result = next(outcomes)
        observed.append(result)
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(checks, 'check_session', check)
    monkeypatch.setattr(checks.time, 'sleep', lambda _: None)
    checks.wait_for_session('light')
    assert len(observed) == 5


@pytest.mark.parametrize('style', ['flat', 'glassy'])
def test_session_rejects_the_other_control_style(monkeypatch, style):
    import json
    monkeypatch.setenv('MTTKDE_WIZARD_OPTIONS', json.dumps({'window_controls': style}))
    other = 'MacTahoe' if style == 'glassy' else 'MacGoldenGate'
    monkeypatch.setattr(checks, '_read', lambda *args: f'__aurorae__svg__{other}LiquidKde-Light')
    with pytest.raises(checks.AppearanceMismatch, match='Window controls'):
        checks.check_session('light')


def test_dock_geometry_rejects_gap_and_clipping():
    import copy
    def widget(name, x, width):
        return {"type": name, "geometry": {"x": x, "y": 8, "width": width, "height": 68}}
    state = [{"location": "bottom", "length": 900, "widgets": [
        widget("org.kde.mac-tahoe-liquid-kde.launcher", 12, 52),
        widget("org.kde.mac.tahoe.liquid.icontasks", 68, 780),
        widget("org.kde.mac-tahoe-liquid-kde.trashcan", 852, 52)]}]
    checks.check_dock_geometry(state)
    gap = copy.deepcopy(state)
    gap[0]["length"] += 44
    gap[0]["widgets"][-1]["geometry"]["x"] += 44
    with pytest.raises(checks.AppearanceMismatch, match="spacing"):
        checks.check_dock_geometry(gap)
    clipped = copy.deepcopy(state)
    clipped[0]["length"] = 829
    with pytest.raises(checks.AppearanceMismatch, match="outside"):
        checks.check_dock_geometry(clipped)
    vertical = copy.deepcopy(state)
    vertical[0]["location"] = "left"
    for widget in vertical[0]["widgets"]:
        g = widget["geometry"]
        g["x"], g["y"], g["width"], g["height"] = g["y"], g["x"], g["height"], g["width"]
    checks.check_dock_geometry(vertical)
    with pytest.raises(checks.AppearanceMismatch, match="No project Dock"):
        checks.check_dock_geometry([])
