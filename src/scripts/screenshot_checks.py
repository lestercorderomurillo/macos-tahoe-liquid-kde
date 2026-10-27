"""Reject mixed appearance in documentation captures. Never repair user settings."""
from __future__ import annotations

import configparser
import statistics
import subprocess
import time
from pathlib import Path


class AppearanceMismatch(RuntimeError):
    pass


def _read(*args: str) -> str:
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE, timeout=10).strip()


def require_virtual_machine() -> None:
    """Documentation capture may change only a disposable guest session."""
    result = subprocess.run(['systemd-detect-virt', '--vm'], capture_output=True, text=True)
    if result.returncode or result.stdout.strip() in ('', 'none'):
        raise RuntimeError('Documentation screenshots require a disposable VM')


def check_session(mode: str, *, home: Path | None = None) -> dict[str, str]:
    """Check each toolkit, including the GTK sheet that settings alone cannot see."""
    if mode not in ('light', 'dark'):
        raise ValueError(mode)
    home = home or Path.home()
    theme = 'MacTahoeLiquidKde-' + mode.capitalize()
    from theme_switch import decoration_theme
    expected = {
        'Window controls': (('kreadconfig6', '--file', 'kwinrc', '--group', 'org.kde.kdecoration2', '--key', 'theme'),
                            '__aurorae__svg__' + decoration_theme(mode)),
        'Plasma': (('kreadconfig6', '--file', 'plasmarc', '--group', 'Theme', '--key', 'name'), theme),
        'Qt': (('kreadconfig6', '--file', 'kdeglobals', '--group', 'General', '--key', 'ColorScheme'), theme.replace('Kde-', 'Kde')),
        'Kvantum': (('kreadconfig6', '--file', 'Kvantum/kvantum.kvconfig', '--group', 'General', '--key', 'theme'),
                    'mac-tahoe-liquid-kde' + ('Dark' if mode == 'dark' else '')),
        'GTK preference': (('gsettings', 'get', 'org.gnome.desktop.interface', 'color-scheme'), "'prefer-" + mode + "'"),
        'GTK theme': (('gsettings', 'get', 'org.gnome.desktop.interface', 'gtk-theme'), repr(theme)),
    }
    observed = {}
    for label, (command, wanted) in expected.items():
        actual = _read(*command)
        if actual != wanted:
            raise AppearanceMismatch(f'{label}: expected {wanted}, got {actual}')
        observed[label] = actual
    for version in ('3.0', '4.0'):
        settings = configparser.ConfigParser(interpolation=None)
        settings.read(home / f'.config/gtk-{version}/settings.ini')
        if settings.get('Settings', 'gtk-theme-name', fallback='') != theme:
            raise AppearanceMismatch(f'GTK {version} settings do not select {theme}')
        if settings.getboolean('Settings', 'gtk-application-prefer-dark-theme', fallback=None) != (mode == 'dark'):
            raise AppearanceMismatch(f'GTK {version} dark preference differs from {mode}')
    actual = (home / '.config/gtk-4.0/gtk.css').read_text().strip()
    # kde-gtk-config can append its palette to a copied theme sheet.
    palette_import = "@import 'colors.css';"
    if actual.endswith(palette_import):
        actual = actual[:-len(palette_import)].rstrip()
    wanted = (home / '.themes' / theme / 'gtk-4.0/gtk.css').read_text().strip()
    from theme_switch import GTK4_ADAPTIVE_CSS, gtk4_legacy_adaptive_css
    if actual == GTK4_ADAPTIVE_CSS.strip():
        imported = home / '.config/gtk-4.0' / f'gtk-{mode.capitalize()}.css'
        if imported.read_text().strip() != wanted:
            raise AppearanceMismatch(f'GTK 4 adaptive sheet imports stale {mode} CSS')
    elif actual.startswith('/* mac-tahoe-liquid-kde: adaptive legacy GTK 4 */'):
        source = home / '.themes' / theme / 'gtk-4.0/gtk-Light.css'
        if actual != gtk4_legacy_adaptive_css(source.read_text(), mode).strip():
            raise AppearanceMismatch('GTK 4 legacy adaptive sheet is stale or customized')
    elif actual != wanted:
        raise AppearanceMismatch(f'GTK 4 stylesheet differs from {theme}; stale or custom CSS must be reviewed')
    observed['GTK 4 stylesheet'] = theme
    return observed


def wait_for_session(mode: str, timeout: float = 15) -> dict[str, str]:
    """Require three consecutive matches so a delayed GTK update cannot slip in."""
    deadline = time.monotonic() + timeout
    matches = 0
    last_error = 'Appearance did not settle'
    while time.monotonic() < deadline:
        try:
            state = check_session(mode)
            matches += 1
            if matches == 3:
                return state
        except (AppearanceMismatch, OSError, subprocess.SubprocessError) as exc:
            matches = 0
            last_error = str(exc)
        time.sleep(.5)
    raise AppearanceMismatch(last_error)


def check_files_pixels(image, mode: str, windows: list[dict], scale: float,
                       *, caption: str = 'Documents') -> dict:
    """Verify the real Files content area, even if all saved settings agree.

    The documentation fixture opens Documents with folders in its first row.
    Sample the empty lower content area, away from sidebar, labels and chrome.
    Do not use this brightness test on glass popups or the mode-neutral Dock.
    """
    if mode not in ('light', 'dark'):
        raise ValueError(mode)
    matches = [w for w in windows if w['resourceClass'] == 'org.gnome.Nautilus'
               and w['caption'] == caption]
    if len(matches) != 1:
        raise AppearanceMismatch(f'Expected one Documents window, found {len(matches)}')
    g = matches[0]['geometry']
    box = tuple(round(value * scale) for value in (
        g['x'] + g['width'] * .60, g['y'] + g['height'] * .65,
        g['x'] + g['width'] * .85, g['y'] + g['height'] * .85))
    if not (0 <= box[0] < box[2] <= image.width and 0 <= box[1] < box[3] <= image.height):
        raise AppearanceMismatch('Files sample lies outside the capture')
    sample = image.crop(box).convert('RGB')
    pixels = sample.load()
    luminance = [.2126*r + .7152*g + .0722*b
                 for y in range(sample.height) for x in range(sample.width)
                 for r, g, b in (pixels[x, y],)]
    median = statistics.median(luminance)
    matching = sum(value > 150 if mode == 'light' else value < 105 for value in luminance) / len(luminance)
    if matching < .95:
        raise AppearanceMismatch(f'Files pixels contradict {mode}: median={median:.1f}, matching={matching:.1%}')
    return {'window': matches[0], 'sample': box, 'median_luminance': median, 'matching_fraction': matching}
