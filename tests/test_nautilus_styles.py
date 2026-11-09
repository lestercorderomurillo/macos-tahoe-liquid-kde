"""Nautilus's ID-to-class migration must retain the shared toolbar styling."""
import re

import pytest

import theme_switch


@pytest.mark.parametrize('mode', ['Light', 'Dark'])
@pytest.mark.parametrize('filename', ['gtk.css', 'gtk-Light.css', 'gtk-Dark.css', 'gtk-dark.css'])
@pytest.mark.parametrize('gtk_version', [(4, 14), (4, 16), (4, 22)])
def test_legacy_and_class_based_nautilus_share_toolbar_rules(repo, monkeypatch, mode, filename, gtk_version):
    monkeypatch.setattr(theme_switch, '_gtk4_version', lambda: gtk_version)
    path = repo / f'src/offline/gtk/MacTahoeLiquidKde-{mode}/gtk-4.0/{filename}'
    css = theme_switch.gtk4_compatible_css(path.read_text())
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    names = {
        '#NautilusPathBar': '.nautilus-pathbar.linked',
        '#NautilusPathButton': '.nautilus-path-button',
        '#NautilusQueryEditor': '.nautilus-query-editor',
    }
    matched = set()
    for selectors, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
        selectors = {selector.strip() for selector in selectors.split(',')}
        for legacy in selectors:
            modern = legacy
            for old, new in names.items():
                modern, count = re.subn(re.escape(old) + r'(?![\w-])', new, modern)
                if count:
                    matched.add(old)
            if modern != legacy:
                assert modern in selectors, f'{mode}: missing {modern}'
    assert matched == set(names)
    for selector in ('.nautilus-pathbar.linked',
                     '.nautilus-pathbar.linked > menubutton > button',
                     '.nautilus-query-editor > menubutton > button'):
        blocks = [body for selectors, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css)
                  if selector in {s.strip() for s in selectors.split(',')}]
        assert any('border-radius: 9999px;' in body for body in blocks), selector


@pytest.mark.parametrize('mode', ['Light', 'Dark'])
@pytest.mark.parametrize('gtk_version', [(4, 14), (4, 16), (4, 22)])
def test_installed_adaptive_pathbar_matches_primary_theme(repo, monkeypatch, mode, gtk_version):
    """A primary-sheet repair must also reach both installed theme variants."""
    monkeypatch.setattr(theme_switch, '_gtk4_version', lambda: gtk_version)

    def pathbar_rules(path):
        css = theme_switch.gtk4_compatible_css(path.read_text())
        css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
        start = css.index('#NautilusPathBar,\n.nautilus-pathbar.linked {')
        end = css.index('#NautilusFileChooser multi-layout-view', start)
        return re.sub(r'\s+', ' ', css[start:end]).strip()

    primary = pathbar_rules(repo / f'src/offline/gtk/MacTahoeLiquidKde-{mode}/gtk-4.0/gtk.css')
    for theme in ('Light', 'Dark'):
        directory = repo / f'src/offline/gtk/MacTahoeLiquidKde-{theme}/gtk-4.0'
        names = [f'gtk-{mode}.css'] + (['gtk-dark.css'] if mode == 'Dark' else [])
        for name in names:
            assert pathbar_rules(directory / name) == primary, (theme, name, gtk_version)
