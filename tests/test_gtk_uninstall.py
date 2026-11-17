"""Uninstall removes proven GTK overrides without deleting user files."""

import shutil

import pytest

from steps import gtk
from theme_switch import GTK4_ADAPTIVE_CSS, gtk4_legacy_adaptive_css


@pytest.fixture
def installed(tmp_path, monkeypatch):
    themes = tmp_path / "themes"
    config = tmp_path / "gtk-4.0"
    source = themes / "MacTahoeLiquidKde-Light/gtk-4.0"
    source.mkdir(parents=True)
    config.mkdir()
    for name, data in {
        "gtk-Light.css": "button { color: red; }\n",
        "gtk-Dark.css": "button { color: white; }\n",
        "assets/owned.svg": "owned artwork",
        "windows-assets/close.svg": "close artwork",
    }.items():
        path = source / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(data)
    shutil.copytree(source, config, dirs_exist_ok=True)
    monkeypatch.setattr(gtk, "DEST_DIR", themes)
    monkeypatch.setattr(gtk, "GTK4_DEST", config)
    monkeypatch.setattr(gtk, "qdbus_call", lambda *args: True)
    monkeypatch.setattr(gtk, "have", lambda _: False)
    monkeypatch.setattr(gtk, "remove_tree", lambda path, *args: shutil.rmtree(path) if path.exists() else False)
    return config


@pytest.mark.parametrize("sheet", ["custom", "adaptive", "legacy", "copy"])
def test_uninstall_preserves_unrelated_files_and_removes_owned_overrides(installed, sheet):
    config = installed
    light = (config / "gtk-Light.css").read_text()
    if sheet == "custom":
        (config / "gtk.css").write_text("button { padding: 17px; }\n")
    elif sheet == "copy":
        (config / "gtk.css").write_text(light + "@import 'colors.css';\n")
    else:
        name = "gtk-Adaptive.css" if sheet == "adaptive" else "gtk-AdaptiveLegacy.css"
        (config / name).write_text(GTK4_ADAPTIVE_CSS if sheet == "adaptive" else gtk4_legacy_adaptive_css(light))
        (config / "gtk.css").symlink_to(name)
    custom = {"assets/user.svg": "user artwork", "windows-assets/close.svg": "edited artwork",
              "colors.css": "/* KDE colors */", "window_decorations.css": "/* user decorations */",
              "gtk-dark.css": "/* custom dark sheet */"}
    if sheet == "custom":
        custom["gtk.css"] = (config / "gtk.css").read_text()
    for name, data in custom.items():
        (config / name).write_text(data)
    gtk.uninstall()
    for name, data in custom.items():
        assert (config / name).read_text() == data
    assert not (config / "assets/owned.svg").exists()
    if sheet != "custom":
        assert not (config / "gtk.css").exists()
        assert not (config / "gtk.css").is_symlink()
    gtk.uninstall()
    for name, data in custom.items():
        assert (config / name).read_text() == data


def test_uninstall_preserves_foreign_symlinks(installed, tmp_path):
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "gtk-Adaptive.css").write_text("custom sheet")
    (installed / "gtk.css").symlink_to(foreign / "gtk-Adaptive.css")
    shutil.rmtree(installed / "assets")
    (installed / "assets").symlink_to(foreign, target_is_directory=True)
    gtk.uninstall()
    assert (installed / "gtk.css").is_symlink()
    assert (installed / "assets").is_symlink()
    assert (foreign / "gtk-Adaptive.css").read_text() == "custom sheet"


def test_uninstall_does_not_claim_edited_adaptive_stylesheet(installed):
    path = installed / 'gtk-Adaptive.css'
    custom = GTK4_ADAPTIVE_CSS + '\nbutton { padding: 17px; }\n'
    path.write_text(custom)
    (installed / 'gtk.css').symlink_to(path)
    gtk.uninstall()
    assert path.read_text() == custom
    assert (installed / 'gtk.css').is_symlink()


def test_uninstall_removes_absolute_link_to_owned_sheet(installed):
    path = installed / 'gtk-Adaptive.css'
    path.write_text(GTK4_ADAPTIVE_CSS)
    (installed / 'gtk.css').symlink_to(path)
    gtk.uninstall()
    assert not path.exists()
    assert not (installed / 'gtk.css').is_symlink()


def test_uninstall_removes_dereferenced_bundled_asset_alias(installed):
    source = gtk.DEST_DIR / 'MacTahoeLiquidKde-Light/gtk-4.0/assets'
    (source / 'alias.svg').symlink_to('owned.svg')
    (installed / 'assets/alias.svg').write_bytes((source / 'alias.svg').read_bytes())
    gtk.uninstall()
    assert not (installed / 'assets/alias.svg').exists()
