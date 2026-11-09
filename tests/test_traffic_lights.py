"""Custom windows and Firefox follow the shared Flat/Glassy selection."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import about_info
import window_controls
from steps import firefox


@pytest.mark.parametrize("edition", ["MacTahoe", "MacGoldenGate"])
def test_firefox_reinstall_changes_controls_without_changing_profile(sandbox, monkeypatch, edition):
    import theme_switch
    monkeypatch.setattr(theme_switch, "default_wallpaper", lambda: edition)
    monkeypatch.setattr(firefox, "HOME", sandbox)
    profile = sandbox / ".mozilla/firefox/test.default"
    profile.mkdir(parents=True)
    (profile / "prefs.js").write_text("// existing preferences\n")
    (profile / "places.sqlite").write_bytes(b"untouched browser data")
    chrome = profile / "chrome"
    chrome.mkdir()
    (chrome / "userChrome.css").write_text("/* my rules */\n")
    original = (firefox._theme_source() / "MacTahoe/titlebuttons/titlebutton-close.svg").read_bytes()
    for style in ("flat", "glassy", "flat"):
        monkeypatch.setenv("MTTKDE_WIZARD_OPTIONS", json.dumps({"window_controls": style}))
        firefox.install()
        installed = chrome / firefox.THEME_DIRNAME / "MacTahoe"
        if style == "flat":
            assert (installed / "titlebuttons/titlebutton-close.svg").read_bytes() == original
        else:
            for folder in ("titlebuttons", "titlebuttons-nord"):
                for suffix, mode, state, button in [
                    ("close", "Light", "active", "close"),
                    ("close-hover-dark-alt", "Dark", "hover", "close"),
                    ("minimize-active", "Light", "pressed", "minimize"),
                    ("backdrop-dark", "Dark", "inactive", "close"),
                    ("unmaximize-backdrop", "Light", "hover-inactive", "restore"),
                ]:
                    assert (installed / folder / f"titlebutton-{suffix}.svg").read_text() == window_controls.button_svg(button, mode, state)
        assert (profile / "places.sqlite").read_bytes() == b"untouched browser data"
        assert (profile / "prefs.js").read_text() == "// existing preferences\n"
    firefox.uninstall()
    assert (chrome / "userChrome.css").read_text() == "/* my rules */\n"
    assert not (chrome / firefox.THEME_DIRNAME).exists()
    assert (firefox._theme_source() / "MacTahoe/titlebuttons/titlebutton-close.svg").read_bytes() == original


def test_about_uses_selected_family_and_config_cascade(sandbox, offline):
    config = sandbox / ".config"
    data = sandbox / ".local/share/aurorae/themes"
    for family in window_controls.EDITIONS:
        for mode in ("Light", "Dark"):
            window_controls.assemble_aurorae(offline / "aurorae", data / f"{family}LiquidKde-{mode}", mode, family)
    defaults = config / "kdedefaults/kwinrc"
    defaults.parent.mkdir()
    defaults.write_text("[org.kde.kdecoration2]\ntheme=__aurorae__svg__MacGoldenGateLiquidKde-Light\n")
    user = config / "kwinrc"
    user.write_text("[Other]\nvalue=1\n")
    assert "MacGoldenGate" in about_info.window_controls()["Light"]
    for family in ("MacTahoe", "MacGoldenGate", "MacTahoe"):
        for mode in ("Light", "Dark", "Light"):
            user.write_text(f"[org.kde.kdecoration2]\ntheme=__aurorae__svg__{family}LiquidKde-{mode}\n")
            assert about_info.window_controls() == {m: str(data / f"{family}LiquidKde-{m}") for m in ("Light", "Dark")}
    user.write_text("[org.kde.kdecoration2]\ntheme=\n")
    assert about_info.window_controls() == {}


def test_wizard_controls_change_immediately_in_both_modes(repo, tmp_path):
    probe = r'''
import sys
from pathlib import Path
sys.path[:0] = [str(Path.cwd() / 'src/scripts'), str(Path.cwd() / 'src/installer')]
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from installer_ui import _make_installer_bridge
from wizard_window import InstallerWindow
import cli
cli._theme_is_already_installed = lambda: False
app = QApplication([])
window = InstallerWindow(_make_installer_bridge())
window.show(); app.processEvents()
for mode in ('white', 'black', 'white'):
    palette = window.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(mode))
    window.setPalette(palette)
    images = []
    for style in ('flat', 'glassy', 'flat'):
        window.select('window_controls', style)
        app.processEvents()
        images.append(window.close_button.grab().toImage())
        window.minimize_button.grab()
    assert images[0] != images[1] and images[0] == images[2]
assert all(not pixmap.isNull() for pixmap in window.close_button._pixmaps.values())
assert any(key[-1] == 'deactivated' for key in window.minimize_button._pixmaps)
'''
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", HOME=str(tmp_path),
               XDG_CONFIG_HOME=str(tmp_path), DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent")
    result = subprocess.run([sys.executable, "-c", probe], cwd=repo, env=env,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_about_qml_uses_selected_artwork_across_mode_changes(repo, offline, tmp_path):
    from PyQt6.QtCore import QLibraryInfo
    imports = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.QmlImportsPath))
    if not (imports / "org/kde/ki18n/qmldir").is_file():
        pytest.skip("KDE QML translations are not installed")
    families = {}
    for family in window_controls.EDITIONS:
        families[family] = {}
        for mode in ("Light", "Dark"):
            dest = tmp_path / f"{family}-{mode}"
            window_controls.assemble_aurorae(offline / "aurorae", dest, mode, family)
            families[family][mode] = str(dest)
    probe = r'''
import sys, json
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine, QQmlComponent, QQmlExpression
from PyQt6.QtQuick import QQuickItem
app = QGuiApplication([])
engine = QQmlApplicationEngine()
host_component = QQmlComponent(engine)
host_component.setData(b'import org.kde.plasma.core as PlasmaCore; PlasmaCore.Dialog { visible: false }', QUrl())
host = host_component.create()
assert host is not None, host_component.errors()
errors = []
engine.warnings.connect(lambda warnings: errors.extend(w.toString() for w in warnings))
engine.setInitialProperties({'visible': False, 'fetcherCommand': 'true', 'controlsCommand': 'true'})
engine.load(QUrl.fromLocalFile(sys.argv[1]))
assert engine.rootObjects(), errors
window = engine.rootObjects()[0]
def evaluate(code):
    expression = QQmlExpression(engine.contextForObject(window), window, code)
    expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
def find(item, name):
    if item.objectName() == name:
        return item
    for child in item.childItems():
        found = find(child, name)
        if found is not None:
            return found
for paths in json.loads(sys.argv[2]).values():
    evaluate('windowControlPaths = ' + json.dumps(paths))
    for mode in ('Light', 'Dark', 'Light'):
        evaluate('Kirigami.Theme.backgroundColor = ' + repr('white' if mode == 'Light' else 'black'))
        app.processEvents()
        assert window.property('windowControlPath') == paths[mode]
        for button in ('close', 'minimize', 'maximize'):
            light = find(window.contentItem(), 'aboutWindowLight-' + button)
            image = find(window.contentItem(), 'aboutWindowLightImage-' + button)
            assert light is not None and image is not None
            assert light.property('artworkAvailable'), (paths, button)
            assert image.property('elementId') == ('inactive-center' if button == 'close' else 'deactivated-center')
assert not errors, '\n'.join(errors)
'''
    qml = offline / "plasmoids/org.kde.mac.tahoe.liquid.globalmenu/qml/AboutWindow.qml"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
               HOME=str(tmp_path), XDG_CONFIG_HOME=str(tmp_path),
               DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent")
    result = subprocess.run([sys.executable, "-c", probe, str(qml), json.dumps(families)],
                            env=env, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
