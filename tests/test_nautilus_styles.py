"""Nautilus's ID-to-class migration must retain the shared toolbar styling."""
import re

import pytest

import theme_switch


@pytest.mark.parametrize('mode', ['Light', 'Dark'])
@pytest.mark.parametrize('gtk_version', [(4, 14), (4, 16)])
def test_legacy_and_class_based_nautilus_share_toolbar_rules(repo, monkeypatch, mode, gtk_version):
    monkeypatch.setattr(theme_switch, '_gtk4_version', lambda: gtk_version)
    path = repo / f'src/offline/gtk/MacTahoeLiquidKde-{mode}/gtk-4.0/gtk.css'
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
