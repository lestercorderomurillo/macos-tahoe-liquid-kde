"""Recognize an owned GTK override while its old installed source still exists."""

import pytest

from steps import gtk
from theme_switch import _gtk4_css_is_replaceable, gtk4_legacy_adaptive_css


@pytest.mark.parametrize("custom", [False, True])
def test_upgrade_retains_ownership_without_claiming_custom_css(tmp_path, monkeypatch, custom):
    themes = tmp_path / "themes"
    source = themes / "MacTahoeLiquidKde-Light/gtk-4.0/gtk-Light.css"
    source.parent.mkdir(parents=True)
    old = "@define-color window_bg_color white;\nbutton { color: red; }\n"
    source.write_text(old)
    config = tmp_path / "gtk-4.0"
    config.mkdir()
    css = config / "gtk.css"
    original = gtk4_legacy_adaptive_css(old) + ("button { padding: 99px; }\n" if custom else "")
    css.write_text(original + "@import 'colors.css';\n")
    before = css.read_bytes()
    monkeypatch.setattr(gtk, "DEST_DIR", themes)
    monkeypatch.setattr(gtk, "GTK4_DEST", config)
    gtk._retain_gtk4_css_ownership(tmp_path / "offline")
    source.write_text("button { color: blue; }\n")
    assert css.read_bytes() == before
    assert css.is_symlink() is not custom
    assert _gtk4_css_is_replaceable(css, themes) is not custom


@pytest.mark.parametrize("custom", [False, True])
def test_accent_upgrade_after_kde_copies_adaptive_css(tmp_path, monkeypatch, custom):
    import theme_switch
    config = tmp_path / ".config/gtk-4.0"
    config.mkdir(parents=True)
    theme = tmp_path / ".themes/MacTahoeLiquidKde-Dark/gtk-4.0"
    theme.mkdir(parents=True)
    old = "@define-color accent_bg_color #c95eff;\nbutton { color: @accent_bg_color; }\n"
    new = old.replace("#c95eff", "#007aff")
    for filename in ("gtk-Light.css", "gtk-Dark.css"):
        (theme / filename).write_text(new)
        (config / filename).write_text(old)
    generated = gtk4_legacy_adaptive_css(old)
    (config / "gtk-AdaptiveLegacy.css").write_text(generated)
    css = config / "gtk.css"
    css.write_text(generated + ("button { padding: 99px; }\n" if custom else ""))
    original = css.read_bytes()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(theme_switch, "_have", lambda _: False)
    monkeypatch.setattr(theme_switch, "_qdbus", lambda *args: True)
    monkeypatch.setattr(theme_switch, "flush_icon_caches", lambda: None)
    monkeypatch.setattr(theme_switch, "_gtk4_supports_media_queries", lambda: False)

    theme_switch._apply_local_extras("dark")

    assert css.is_symlink() is not custom
    assert css.read_bytes() == (original if custom else gtk4_legacy_adaptive_css(new).encode())
    assert (config / "gtk-Light.css").read_text() == new
