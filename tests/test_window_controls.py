"""Edition selection, complete Aurorae packages and GTK/Aurorae parity."""

import json
import re
import shutil
from xml.etree import ElementTree as ET

import pytest

import window_controls as controls
import theme_switch


@pytest.mark.parametrize("mode", ["Light", "Dark"])
def test_all_controls_render_every_interaction_state(mode):
    from PyQt6.QtCore import QByteArray, QRectF
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer

    for button in controls.BUTTONS:
        sheet = controls.button_svg(button, mode)
        root = ET.fromstring(sheet)
        ids = [node.get("id") for node in root.iter() if node.get("id")]
        assert len(ids) == len(set(ids))
        renderer = QSvgRenderer(QByteArray(sheet.encode()))
        assert renderer.isValid()
        pixels = {}
        for state in controls.STATES:
            element = state + "-center"
            assert renderer.elementExists(element)
            assert renderer.boundsOnElement(element).width() == 16
            image = QImage(32, 32, QImage.Format.Format_ARGB32)
            image.fill(0)
            painter = QPainter(image)
            renderer.render(painter, element, QRectF(0, 0, 32, 32))
            painter.end()
            assert image.pixelColor(16, 16).alpha() > 50
            assert image.pixelColor(0, 0).alpha() == 0
            pixels[state] = image.constBits().asstring(image.sizeInBytes())
        assert pixels["active"] != pixels["inactive"] != pixels["deactivated"]
        assert pixels["active"] != pixels["hover"] != pixels["pressed"]
        assert pixels["hover"] == pixels["hover-inactive"]


@pytest.mark.parametrize("edition", controls.EDITIONS)
@pytest.mark.parametrize("style", ("flat", "glassy"))
def test_install_reinstall_switch_and_uninstall(repo, tmp_path, monkeypatch, edition, style):
    from steps import window_decorations as step
    from window_shadows import aurorae_svg
    destination = tmp_path / "aurorae"
    monkeypatch.setattr(step, "DEST_DIR", destination)
    monkeypatch.setattr(step, "qdbus_call", lambda *args: True)
    monkeypatch.setattr(theme_switch, "default_wallpaper", lambda: edition)
    writes = []
    monkeypatch.setattr(step, "kw_write", lambda *args: writes.append(args) or True)
    monkeypatch.setenv("MTTKDE_WIZARD_OPTIONS", json.dumps({"shadows": "soft", "window_controls": style}))
    family = "MacGoldenGate" if style == "glassy" else "MacTahoe"

    for mode in ("light", "dark", "light"):
        monkeypatch.setattr(step, "theme_mode", lambda: mode)
        step.install()
        assert any(args[-2:] == ("theme", f"__aurorae__svg__{family}LiquidKde-{mode.title()}")
                   for args in writes)
        for prefix in controls.EDITIONS:
            for variant in ("Light", "Dark"):
                name = f"{prefix}LiquidKde-{variant}"
                package = destination / name
                rc = (package / f"{name}rc").read_text()
                assert "TitleEdgeTop=8" in rc  # Preserve shared title-bar geometry.
                assert f"ButtonSpacing={7 if prefix == 'MacGoldenGate' else 10}" in rc
                assert json.loads((package / "metadata.json").read_text())["KPlugin"]["Id"] == name
                original = repo / f"src/offline/aurorae/MacTahoeLiquidKde-{variant}/decoration.svg"
                assert (package / "decoration.svg").read_text() == aurorae_svg(original.read_text(), "soft")
                if prefix == "MacTahoe":
                    assert (package / "close.svg").read_bytes() == (
                        repo / f"src/offline/aurorae/icons-{variant}/close.svg").read_bytes()
                else:
                    assert (package / "close.svg").read_text() == controls.button_svg("close", variant)
                    for button in ("alldesktops", "keepabove", "keepbelow"):
                        assert (package / f"{button}.svg").read_bytes() == (
                            repo / f"src/offline/aurorae/icons-{variant}/{button}.svg").read_bytes()
    from steps import global_theme
    monkeypatch.setattr(global_theme, "DEST_DIR", tmp_path / "look-and-feel")
    monkeypatch.setattr(global_theme, "install_tree", lambda src, dst, name:
                        shutil.copytree(src, dst, dirs_exist_ok=True))
    global_theme.install()
    for variant in ("light", "dark"):
        defaults = (global_theme.DEST_DIR / f"org.kde.mac-tahoe-liquid-kde.{variant}/contents/defaults").read_text()
        assert f"theme=__aurorae__svg__{family}LiquidKde-{variant.title()}" in defaults
    custom = destination / "Custom"
    custom.mkdir()
    step.uninstall()
    assert list(destination.iterdir()) == [custom]


@pytest.mark.parametrize("mode", ["Light", "Dark"])
def test_gtk_controls_use_same_artwork_and_leave_other_assets_alone(repo, tmp_path, monkeypatch, mode):
    source = repo / f"src/offline/gtk/MacTahoeLiquidKde-{mode}"
    theme = tmp_path / source.name
    for version in (3, 4):
        shutil.copytree(source / f"gtk-{version}.0", theme / f"gtk-{version}.0")
    original = {p.relative_to(theme): p.read_bytes() for p in theme.rglob("*.css")}
    monkeypatch.setattr(theme_switch, "default_wallpaper", lambda: "MacTahoe")
    controls.apply_gtk_controls(theme)
    assert all((theme / p).read_bytes() == data for p, data in original.items())
    monkeypatch.setattr(theme_switch, "default_wallpaper", lambda: "MacGoldenGate")
    controls.apply_gtk_controls(theme)
    for path, data in original.items():
        css = theme / path
        text = css.read_text()
        assert '-gtk-scaled(url("windows-assets/titlebutton-' not in text
        # Each replacement resolves to a real, scalable state, without touching
        # margins, focus selectors, unrelated icons or background colors.
        urls = re.findall(r'url\("(windows-assets/golden-gate-[^"\n]+)"\)', text)
        for url in urls:
            assert (css.parent / url).is_file()
        old_rules = re.sub(r'background-image: [^;]+;', '', data.decode())
        new_rules = re.sub(r'background-image: [^;]+;', '', text)
        assert old_rules == new_rules
    for version in (3, 4):
        assert (theme / f"gtk-{version}.0/windows-assets/golden-gate-close-dark.svg").read_text() == controls.button_svg("close", "Dark", "active")
    light = (theme / "gtk-4.0/gtk-Light.css").read_text()
    for appearance in ("light", "dark", "light"):
        adaptive = theme_switch.gtk4_legacy_adaptive_css(light, appearance)
        references = re.findall(r'windows-assets/golden-gate-[\w-]+\.svg', adaptive)
        assert references and all(url.endswith(f"-{appearance}.svg") for url in references)
        assert all((theme / "gtk-4.0" / url).is_file() for url in references)
        custom = tmp_path / "gtk.css"
        custom.write_text(adaptive)
        assert theme_switch._gtk4_css_is_replaceable(custom, tmp_path)
    first = {p: p.read_bytes() for p in theme.rglob("*.css")}
    controls.apply_gtk_controls(theme)
    assert all(p.read_bytes() == data for p, data in first.items())


@pytest.mark.parametrize("edition", controls.EDITIONS)
def test_standalone_switcher_retains_decoration_edition(repo, tmp_path, monkeypatch, edition):
    import importlib.util
    script = tmp_path / "mac-tahoe-theme-switch"
    source = (repo / "src/scripts/theme_switch.py").read_text()
    script.write_text(source.replace('DEFAULT_WALLPAPER = "MacTahoe"', f'DEFAULT_WALLPAPER = "{edition}"'))
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("installed_switcher", str(script))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    # An unrelated defaults file beside an installed command cannot change it.
    (tmp_path / "defaults.json").write_text('{"wallpaper": "MacTahoe"}')
    writes = []
    monkeypatch.setattr(module, "_have", lambda cmd: cmd == "kwriteconfig6")
    monkeypatch.setattr(module, "_kwrite", lambda *args: writes.append(args) or True)
    monkeypatch.setattr(module, "apply_color_scheme", lambda scheme: True)
    for mode in ("light", "dark", "light"):
        assert module.decoration_theme(mode) == f"{edition}LiquidKde-{mode.title()}"
        writes.clear()
        assert module.write_kde_theme_config(mode)
        assert any(args[-2:] == ("theme", f"__aurorae__svg__{edition}LiquidKde-{mode.title()}")
                   for args in writes)


@pytest.mark.parametrize("edition", controls.EDITIONS)
@pytest.mark.parametrize("style", ("flat", "glassy"))
def test_explicit_style_overrides_edition_for_gtk_and_installed_switcher(repo, tmp_path, monkeypatch, edition, style):
    import importlib.util
    from importlib.machinery import SourceFileLoader
    monkeypatch.setattr(theme_switch, "default_wallpaper", lambda: edition)
    monkeypatch.setenv("MTTKDE_WIZARD_OPTIONS", json.dumps({"window_controls": style}))
    family = "MacGoldenGate" if style == "glassy" else "MacTahoe"
    source = repo / "src/offline/gtk/MacTahoeLiquidKde-Light"
    theme = tmp_path / "theme"
    shutil.copytree(source / "gtk-4.0", theme / "gtk-4.0")
    controls.apply_gtk_controls(theme)
    css = (theme / "gtk-4.0/gtk.css").read_text()
    assert ("golden-gate-close" in css) == (style == "glassy")
    script = tmp_path / "mac-tahoe-theme-switch"
    text = (repo / "src/scripts/theme_switch.py").read_text()
    text = text.replace('DEFAULT_WALLPAPER = "MacTahoe"', f'DEFAULT_WALLPAPER = "{edition}"')
    text = text.replace('INSTALLER_OPTIONS = {}', f'INSTALLER_OPTIONS = {{"window_controls": "{style}"}}')
    script.write_text(text)
    loader = SourceFileLoader("style_switcher", str(script))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    # An unrelated launch environment must not override the installed choice.
    monkeypatch.setenv("MTTKDE_WIZARD_OPTIONS", '{"window_controls":"other"}')
    for mode in ("light", "dark", "light"):
        assert module.decoration_theme(mode) == f"{family}LiquidKde-{mode.title()}"
