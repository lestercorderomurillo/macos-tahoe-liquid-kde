"""Wizard choices, native navigation and their backend effects, without a desktop install."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

import installer_choices as choices


@pytest.mark.parametrize("edition", ["MacTahoe", "MacGoldenGate", "MacTahoe"])
def test_new_wizard_uses_source_defaults_after_other_edition(monkeypatch, tmp_path, edition):
    import launcher_defaults
    import cli
    source = tmp_path / "defaults.json"
    source.write_text(json.dumps({"wallpaper": edition}))
    monkeypatch.setattr(launcher_defaults, "DEFAULTS_FILE", source)
    stale = dict(cli.DEFAULT_FEATURES, theme_mode="dark", icons=False, apply_theme=False)
    config = tmp_path / "features.json"
    config.write_text(json.dumps(stale))
    monkeypatch.setattr(cli, "CONFIG_FILE", config)
    expected = "golden" if edition == "MacGoldenGate" else "tahoe"
    selected = choices.defaults()
    assert selected["wallpaper"] == selected["launcher"] == expected
    assert selected["appearance"] == "auto"
    assert selected["window_controls"] == ("glassy" if edition == "MacGoldenGate" else "flat")
    assert selected["reset_layout"]
    assert choices.features(selected, cli.DEFAULT_FEATURES, existing_install=True)["layout"]
    actual = choices.features(selected, cli.DEFAULT_FEATURES)
    assert actual["apply_theme"] and actual["icons"]
    assert actual["theme_mode"] == "auto"
    assert json.loads(config.read_text()) == stale  # Opening is read-only.


@pytest.mark.parametrize("payload", [[], {"shell": "echo bad"}, {"icons": "unknown"}, {"shadows": "unknown"}, {"window_controls": "unknown"},
                                    {"fonts": "false"}, {"oled_interval": True},
                                    {"oled_max_shift": 17}, {"wallpaper": "custom"}])
def test_reject_invalid_selections_before_install(payload):
    with pytest.raises(ValueError):
        choices.validate(payload)


def test_control_previews_are_lossless_vm_crops_with_verified_hashes(repo):
    import hashlib
    from PIL import Image
    folder = repo / 'src/installer/assets'
    sources = json.loads((folder / 'sources.json').read_text())
    for style in ('flat', 'glassy'):
        for mode in ('light', 'dark'):
            record = sources[f'window-controls-{style}-{mode}.png']
            path = folder / record['file']
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            assert checksum == record['sha256'] and checksum[:12] in path.name
            assert record['window']['active']
            assert 'dolphin' in record['window']['resourceClass'].lower()
            assert record['scale'] == 4 and len(record['source_sha256']) == 64
            with Image.open(path) as image:
                assert image.format == 'PNG'
                assert image.width >= 724 and image.height >= 380


def test_preserve_options_and_mandatory_components():
    import cli
    selected = choices.defaults() | dict(icons="keep", wallpaper="keep", fonts=False,
                                        panel=False, dock=True, files="dolphin")
    actual = choices.features(selected, cli.DEFAULT_FEATURES)
    assert not any(actual[key] for key in ("icons", "wallpapers", "fonts", "nautilus", "nautilus_bookmarks"))
    assert actual["layout"]
    assert all(actual[key] for key in ("globalmenu", "global_theme", "gtk", "kvantum",
                                      "cursors", "sounds", "portals", "apply_theme"))
    assert not actual["sddm"]


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("reset", [False, True])
def test_layout_reset_respects_the_selected_option(existing, reset):
    import cli
    selected = choices.defaults() | {"reset_layout": reset}
    actual = choices.features(selected, cli.DEFAULT_FEATURES, existing_install=existing)
    assert actual["layout"] == (not existing or reset)
    assert actual["plasmoids"] and actual["apply_theme"]
    assert choices.defaults()["reset_layout"]


def test_keep_file_manager_excludes_nautilus_and_bookmarks():
    import cli
    actual = choices.features(choices.defaults() | {"files": "keep"}, cli.DEFAULT_FEATURES)
    assert not actual["nautilus"] and not actual["nautilus_bookmarks"]


def test_choices_survive_privilege_boundary_as_one_quoted_argument(monkeypatch):
    import installer_ui
    monkeypatch.setattr(installer_ui.shutil, "which", lambda _: "/usr/bin/pkexec")
    selected = choices.defaults() | {"wallpaper": "custom", "wallpaper_path": "/tmp/a ' $(touch bad); image.jpg"}
    command = installer_ui.escalated_command_for_action(
        "install", headless=True, progress_file="/tmp/progress", cancel_file="/tmp/cancel", choices=selected)
    argv = shlex.split(command)
    assert json.loads(argv[argv.index("--wizard-options")+1]) == selected
    assert any(arg.endswith("/src/scripts/installer_backend.py") for arg in argv)
    assert "./install" not in argv


def test_accent_changes_blue_selection_but_preserves_status_and_alpha():
    from theme_accent import recolor
    original = 'fill:#007aff; color:#ff3b30; background:rgba(0,122,255,0.35); neutral:#808080;'
    actual = recolor(original, "#28cd41")
    assert "#007aff" not in actual
    assert "#ff3b30" in actual and "#808080" in actual and ",0.35)" in actual
    geometry = 'transform="matrix(0.62500095,0,0,4,34.124967,-2712.0865)" d="M 0,122,255 4,5,6"'
    assert recolor(geometry, "#007aff") == geometry
    config = '[Colors:Selection]\nBackgroundNormal=0,122,255\nForegroundNormal=255,255,255\n'
    tinted = recolor(config, "#28cd41")
    assert 'BackgroundNormal=0,122,255' not in tinted
    assert 'ForegroundNormal=255,255,255' in tinted


def test_all_accent_colors_preserve_bundled_svg_geometry(repo):
    import gzip
    from xml.etree import ElementTree as ET
    from theme_accent import recolor

    geometry = {'d', 'points', 'transform', 'viewBox', 'x', 'y', 'width', 'height',
                'rx', 'ry', 'r', 'cx', 'cy', 'x1', 'x2', 'y1', 'y2', 'offset', 'id'}
    def shapes(text):
        return [(node.tag, {k: v for k, v in node.attrib.items() if k in geometry})
                for node in ET.fromstring(text).iter()]

    checked = 0
    for folder in ('plasma-theme', 'kvantum/mac-tahoe-liquid-kde', 'gtk'):
        for path in (repo / 'src/offline' / folder).rglob('*'):
            if path.is_symlink() or path.suffix not in ('.svg', '.svgz'):
                continue
            data = path.read_bytes()
            original = (gzip.decompress(data) if path.suffix == '.svgz' else data).decode()
            expected = shapes(original)
            for color in choices.COLORS.values():
                assert shapes(recolor(original, color)) == expected, (path, color)
            checked += 1
    assert checked > 100


def test_layout_uses_explicit_launcher_and_independent_panels(monkeypatch, tmp_path):
    from steps import layout
    monkeypatch.setattr(layout, "HOME", tmp_path)
    monkeypatch.setattr(layout, "_discover_is_installed", lambda: True)
    monkeypatch.setenv("MTTKDE_WIZARD_OPTIONS", json.dumps(choices.defaults() | {
        "launcher": "golden", "panel": False, "dock": True}))
    script = layout._layout_script_with_launchers(layout.LAYOUT_SCRIPT, ["applications:example.desktop"], "icontasks")
    assert "var mttkdeLauncherPreset = 2;" in script
    assert "var mttkdeTopPanel = false;" in script and "var mttkdeDock = true;" in script
    assert "applications:example.desktop" in script


def test_installed_switcher_uses_selected_wallpaper_pair_and_icon_mode(monkeypatch, tmp_path):
    import theme_switch as switch
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    for name in choices.WALLPAPERS["landscape"]:
        (tmp_path / "wallpapers" / name).mkdir(parents=True)
    monkeypatch.setattr(switch, "INSTALLER_OPTIONS", choices.defaults() | {"wallpaper": "landscape", "icons": "glass"})
    assert switch._wallpaper_path("light").name == "MacTahoe-Landscape-Morning"
    assert switch._wallpaper_path("dark").name == "MacTahoe-Landscape-Night"
    writes = []
    monkeypatch.setattr(switch, "_have", lambda _: True)
    monkeypatch.setattr(switch, "_kwrite", lambda *args: writes.append(args) or True)
    monkeypatch.setattr(switch, "apply_color_scheme", lambda _: True)
    assert switch.write_kde_theme_config("dark")
    assert any(args[-1] == "MacTahoeLiquidKde-Icons-Glass-Dark" for args in writes)
    writes.clear()
    assert switch.write_kde_theme_config("light")
    assert any(args[-1] == "MacTahoeLiquidKde-Icons-Glass-Light" for args in writes)


@pytest.mark.parametrize("edition", ["MacTahoe", "MacGoldenGate"])
def test_native_wizard_navigation_preserves_choices_and_waits_for_completion(repo, tmp_path, edition):
    # QApplication cannot replace the QCoreApplication used by bridge tests.
    script = r'''
import sys
from pathlib import Path
sys.path[:0] = [str(Path.cwd() / 'src/scripts'), str(Path.cwd() / 'src/installer')]
from PyQt6.QtWidgets import QApplication, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from installer_ui import _make_installer_bridge
from wizard_window import InstallerWindow, ChoiceCard, STEPS, ASSETS
import installer_choices
import cli
cli._theme_is_already_installed = lambda: False
installer_choices.edition_name = lambda: sys.argv[1]
app = QApplication([])
from PyQt6.QtGui import QPalette, QColor
system_palette = app.palette()
for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base, QPalette.ColorRole.Button):
    system_palette.setColor(role, QColor('#111111'))
for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
    system_palette.setColor(role, QColor('#eeeeee'))
app.setPalette(system_palette)
bridge = _make_installer_bridge()
bridge._language = 'es'
bridge.__class__.editionName = property(lambda _: sys.argv[1])
calls = []
def start(action):
    calls.append((action, dict(bridge._choices)))
    bridge._running = True
bridge.start = start
window = InstallerWindow(bridge)
window.show(); app.processEvents()
assert app.palette().window().color().name() == '#111111'
assert window.palette().window().color().name() == '#111111'
assert window.grab().toImage().pixelColor(10, 60).name() == '#292929'
assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
from wizard_window import WindowLight
lights = window.header.findChildren(WindowLight)
assert len(lights) == 3
assert [light.isEnabled() for light in lights] == [True, False, False]
assert [light.x() for light in lights] == [14, 38, 62]
assert all(light.y() == 14 and light.width() == light.height() == 16 for light in lights)
assert window.close_button.accessibleName() == window.t('Close')
assert window.next.hasFocus()
assert all(not pixmap.isNull() for light in lights for pixmap in light._pixmaps.values())
assert abs(window.welcome_actions.mapTo(window, window.welcome_actions.rect().center()).x() - window.width()/2) <= 2
window.language.setCurrentIndex(window.language.findData('de')); app.processEvents()
assert bridge.language == 'de'
window.language.setCurrentIndex(window.language.findData('es')); app.processEvents()
assert bridge.language == 'es'
for page, _ in STEPS:
    window.page = page; window.render(); app.processEvents(); app.processEvents()
    assert window.scroll.horizontalScrollBar().maximum() == 0, page
    assert window.scroll.verticalScrollBar().maximum() == 0, page
    assert window.content.findChild(type(window.label('')), 'pageTitle') is not None or page == 'welcome'
    cards = window.content.findChildren(ChoiceCard)
    if page in ('appearance', 'icons', 'wallpaper', 'launcher', 'window_controls', 'fonts', 'files'):
        assert cards and cards[0].isChecked(), page
        assert cards[0].height() > 80, page
window.page = 'welcome'; window.render(); app.processEvents()
assert window.express.isVisible()
assert window.express.x() > window.language.x() + window.language.width()
window.choices.update(icons='keep', appearance='dark', launcher='other')
window.updating = True; window.express_install()
assert window.page == 'welcome' and not calls
window.updating = False
window.express.click(); app.processEvents()
assert window.page == 'summary' and window.choices == window.defaults and not calls
assert not window.express.isVisible()
window.express_install()
assert window.page == 'summary' and not calls
window.advance()
assert calls == [('install', window.defaults)]
bridge._running = False; bridge.finished.emit(0)
calls.clear()
window.page = 'welcome'; window.render(); window.advance()
assert window.page == 'appearance' and not calls
window.page = 'files'; window.render(); app.processEvents()
from wizard_window import CheckOption, RadioOption
bookmarks = window.content.findChild(CheckOption, 'choice-nautilus_bookmarks')
assert bookmarks.isChecked()
bookmarks.setFocus(); QTest.keyClick(bookmarks, Qt.Key.Key_Space)
assert not window.choices['nautilus_bookmarks']
for page, key in [('firefox', 'firefox'), ('boot', 'plymouth')]:
    window.page = page; window.render(); app.processEvents(); app.processEvents()
    options = window.content.findChildren(RadioOption)
    assert len(options) == 2 and options[0].y() == options[1].y()
    assert abs(options[0].width() - options[1].width()) <= 1
    options[1].click(); app.processEvents()
    assert window.choices[key] is False
window.page = 'launcher'; window.render()
cards = window.content.findChildren(ChoiceCard)
first = cards[0].accessibleName()
cards[1].click(); app.processEvents(); app.processEvents()
assert window.content.findChildren(ChoiceCard)[0].accessibleName() == first
selected = window.choices['launcher']
# Selection does not shift card edges, and dots stay centered despite unequal button labels.
cards = window.content.findChildren(ChoiceCard)
assert cards[0].y() == cards[1].y()
assert cards[0].height() == cards[1].height()
assert abs(window.dots.mapTo(window, window.dots.rect().center()).x() - window.width()/2) <= 2
window.page = 'window_controls'; window.render(); app.processEvents()
window.content.findChild(ChoiceCard, 'choice-window_controls-glassy').click()
assert window.choices['window_controls'] == 'glassy'
window.page = 'summary'; window.render(); app.processEvents()
window.content.findChild(QPushButton, 'edit-window_controls').click()
assert window.page == 'window_controls'
window.content.findChild(ChoiceCard, 'choice-window_controls-flat').click()
window.advance(); app.processEvents()
assert window.page == 'summary' and window.choices['window_controls'] == 'flat'
window.page = 'icons'; window.render(); app.processEvents()
window.content.findChild(ChoiceCard, 'choice-icons-keep').click(); app.processEvents()
assert window.choices['icons'] == 'keep'
assert sum(card.isChecked() for card in window.content.findChildren(ChoiceCard)) == 1
window.content.findChild(QPushButton, 'color-green').click(); app.processEvents()
assert window.choices['color'] == 'green'

window.page = 'summary'; window.render()
window.content.findChild(QPushButton, 'edit-icons').click()
assert window.page == 'icons'
window.select('icons', 'glass'); app.processEvents(); window.advance()
assert window.page == 'summary' and window.choices['launcher'] == selected
window.advance()
assert window.page == 'progress' and calls[-1][0] == 'install'
bridge._handle_record('13\tInstalling Icons\tInstalling Icons')
step_index, progress = bridge._step_index, bridge.progress
for completed in (0, 100, 6366):
    message = f'Generating icons: {completed}/6366'
    bridge._handle_record('__STATUS__\t' + message)
    app.processEvents()
    assert window.step_label.text() == message
    assert bridge._step_index == step_index and bridge.progress == progress
    assert bridge.running and window.page == 'progress'
bridge._handle_record('14\tInstalling fonts\tInstalling fonts')
assert bridge._step_index == step_index + 1
assert window.step_label.text() == 'Installing fonts'
assert calls[-1][1]['icons'] == 'glass'
bridge._running = False; bridge.finished.emit(0)
assert window.page == 'done'
window.page = 'uninstall'; window.render(); window.advance()
assert calls[-1][0] == 'uninstall' and window.page == 'progress'
bridge._running = False; bridge.finished.emit(1)
assert window.page == 'error'
window.advance()
assert calls[-1][0] == 'uninstall'
bridge.runningChanged.emit()
assert not window.close_button.isEnabled()
QTest.mouseClick(window.close_button, Qt.MouseButton.LeftButton)
assert not window.close_pending and window.isVisible()
window.close()
assert window.close_pending and window.isVisible()
bridge._running = False; bridge.finished.emit(130)
app.processEvents()
assert not window.isVisible()
window.show(); window.render(); app.processEvents()
QTest.mouseClick(window.close_button, Qt.MouseButton.LeftButton)
assert not window.isVisible()
# Repeated option changes must keep the visible page and its controls alive.
# This catches both immediate rebuilds and zero-delay render callbacks.
window = InstallerWindow(bridge)
window.show(); app.processEvents()
from PyQt6.QtWidgets import QSpinBox, QFileDialog
from PyQt6.QtGui import QPixmap, QColor
from PyQt6.QtCore import QObject, QEvent
class PageEvents(QObject):
    def __init__(self):
        super().__init__(); self.hidden = 0
    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Hide:
            self.hidden += 1
        return False
for page in ('appearance', 'icons', 'wallpaper', 'launcher', 'layout', 'effects',
             'fonts', 'firefox', 'files', 'boot', 'oled'):
    window.page = page; window.render(); app.processEvents(); app.processEvents()
    content = window.content
    observer = PageEvents(); content.installEventFilter(observer)
    controls = content.findChildren(ChoiceCard) + content.findChildren(RadioOption)
    if page == 'icons':
        controls += [content.findChild(QPushButton, 'color-green'), content.findChild(QPushButton, 'color-red')]
    for control in controls + controls[::-1]:
        control.setFocus(); QTest.mouseClick(control, Qt.MouseButton.LeftButton)
        app.processEvents(); app.processEvents()
        assert window.content is content and window.scroll.widget() is content, page
        background = window.grab().toImage().pixelColor(10, 60)
        assert background.name() == '#292929' and background.alpha() == 255, page
        assert not observer.hidden and content.isVisible(), page
        assert control.hasFocus(), (page, control.objectName())
        assert window.scroll.horizontalScrollBar().maximum() == 0, page
        assert window.scroll.verticalScrollBar().maximum() == 0, page
    content.removeEventFilter(observer)
window.page = 'icons'; window.render(); app.processEvents()
photo = window.glass_preview
regular = window.content.findChild(ChoiceCard, 'choice-icons-regular').photo
regular_image = regular.pixmap.toImage()
window.select('color', 'blue')
before = photo.pixmap.toImage(); before_accent = window.accent_preview.pixmap().toImage()
window.select('color', 'green'); app.processEvents()
assert photo is window.glass_preview and photo.pixmap.toImage() != before
assert window.accent_preview.pixmap().toImage() != before_accent
assert regular.pixmap.toImage() == regular_image
assert window.color_buttons['green'].isChecked() and not window.color_buttons['blue'].isChecked()
window.select('icons', 'glass')
assert window.icon_caption.text() == window.t('Icons, selections, top bar and Dock.')
window.select('icons', 'keep')
assert sum(card.isChecked() for card in window.content.findChildren(ChoiceCard)) == 1
window.page = 'wallpaper'; window.render(); app.processEvents()
content = window.content
import tempfile
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / 'wallpaper.png'
    pixmap = QPixmap(10, 10); pixmap.fill(QColor('red')); pixmap.save(str(path))
    original_dialog = QFileDialog.getOpenFileName
    QFileDialog.getOpenFileName = lambda *args: (str(path), '')
    window.choose_file()
    QFileDialog.getOpenFileName = original_dialog
    app.processEvents()
    assert window.content is content and window.choices['wallpaper'] == 'custom'
    assert window.wallpaper_filename.isVisible() and window.wallpaper_filename.text() == path.name
    assert not any(card.isChecked() for card in content.findChildren(ChoiceCard))
    window.select('wallpaper', 'keep')
    assert not window.wallpaper_filename.isVisible()
    window.select('wallpaper', 'tahoe')
    assert not content.findChild(RadioOption).isChecked()
window.page = 'files'; window.render(); app.processEvents()
bookmarks = window.bookmarks
bookmarks.setChecked(False)
window.select('files', 'dolphin'); assert not bookmarks.isVisible()
window.select('files', 'nautilus'); assert bookmarks.isVisible() and not bookmarks.isChecked()
window.content.findChild(RadioOption, 'choice-files-keep').click(); app.processEvents()
assert window.choices['files'] == 'keep' and not bookmarks.isVisible()
assert not any(card.isChecked() for card in window.content.findChildren(ChoiceCard))
window.page = 'summary'; window.render(); app.processEvents()
assert window.choices['files'] == 'keep'
window.existing_install = True
window.page = 'layout'; window.render(); app.processEvents()
cards = window.content.findChildren(ChoiceCard)
reset = window.content.findChild(CheckOption, 'choice-reset_layout')
assert reset.isChecked() and all(card.isEnabled() for card in cards)
reset.click(); app.processEvents()
assert not window.choices['reset_layout'] and all(not card.isEnabled() for card in cards)
window.page = 'summary'; window.render(); app.processEvents()
window.page = 'layout'; window.render(); app.processEvents()
cards = window.content.findChildren(ChoiceCard)
reset = window.content.findChild(CheckOption, 'choice-reset_layout')
assert not reset.isChecked() and all(not card.isEnabled() for card in cards)
reset.click(); app.processEvents()
assert window.choices['reset_layout'] and all(card.isEnabled() for card in cards)
assert window.scroll.verticalScrollBar().maximum() == 0
window.page = 'effects'; window.render(); app.processEvents()
assert window.choices['shadows'] == 'medium'
options = window.content.findChildren(RadioOption)
assert len(options) == 4 and options[0].objectName() == 'choice-shadows-medium'
for level in ['none', 'soft', 'medium', 'hard']:
    window.content.findChild(RadioOption, 'choice-shadows-' + level).click()
    assert window.choices['shadows'] == level
assert window.scroll.verticalScrollBar().maximum() == 0
window.page = 'summary'; window.render(); app.processEvents()
assert window.choices['shadows'] == 'hard'
window.page = 'oled'; window.render(); app.processEvents()
spins = window.content.findChildren(QSpinBox)
window.select('oled_care', True); assert all(spin.isEnabled() for spin in spins)
spins[0].setValue(17)
window.select('oled_care', False); assert all(not spin.isEnabled() for spin in spins)
window.select('oled_care', True); assert spins[0].value() == 17
window.close()
print('native wizard flow passed')
'''
    env = os.environ | {"QT_QPA_PLATFORM": "offscreen", "XDG_CONFIG_HOME": str(tmp_path),
                        "MAC_TAHOE_NO_UPDATE_CHECK": "true", "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-c", script, edition], cwd=repo, env=env,
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr


def test_public_entry_points_do_not_start_a_terminal_installer(repo):
    for name in ("installer", "install", "uninstall"):
        text = (repo / name).read_text()
        assert "from installer_ui import main" in text
        assert "run_install" not in text and "run_uninstall" not in text
    for name in ("legacy-install", "legacy-uninstall", "src/scripts/install_tui.py"):
        assert not (repo / name).exists()


def test_wizard_catalogs_have_the_same_translated_messages():
    from wizard_translations import CATALOGS
    source = set(CATALOGS["es"])
    for catalog in CATALOGS.values():
        assert set(catalog) == source and all(value.strip() for value in catalog.values())
