"""Edition defaults and preset preservation when Plasma rebuilds panels."""

import json
from pathlib import Path
import os
import sys
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

import pytest

import launcher_defaults
from steps import plasmoids


@pytest.mark.parametrize("preset", [1, 2])
@pytest.mark.parametrize("wallpaper", ["MacTahoe", "MacGoldenGate"])
def test_installed_launcher_uses_edition_default_without_changing_source(
        repo, tmp_path, monkeypatch, preset, wallpaper):
    defaults = tmp_path / "defaults.json"
    defaults.write_text(json.dumps({"launcher_preset": preset, "wallpaper": wallpaper}))
    monkeypatch.setattr(launcher_defaults, "DEFAULTS_FILE", defaults)
    widget = repo / "src/offline/plasmoids" / launcher_defaults.LAUNCHER_ID
    original = (widget / "contents/config/main.xml").read_bytes()
    original_view = (widget / "contents/ui/MainView.qml").read_bytes()
    monkeypatch.setattr(plasmoids, "DATA_HOME", tmp_path / "data")
    monkeypatch.setattr(plasmoids, "DEST_DIR", tmp_path / "installed")
    monkeypatch.setattr(plasmoids, "HOME", tmp_path)

    def install_tree(source, destination, label):
        shutil.copytree(source, destination)
        return True

    monkeypatch.setattr(plasmoids, "install_tree", install_tree)
    assert plasmoids._install_launcher_package(widget)
    installed = tmp_path / "installed" / widget.name / "contents/config/main.xml"
    ns = {"k": "http://www.kde.org/standards/kcfg/1.0"}
    root = ET.parse(installed)
    assert root.find(".//k:entry[@name='defaultLauncherPreset']/k:default", ns).text == str(preset)
    assert root.find(".//k:entry[@name='launcherPreset']/k:default", ns).text == "0"
    assert (widget / "contents/config/main.xml").read_bytes() == original
    view = installed.parent.parent / "ui/MainView.qml"
    golden_gate = str(wallpaper == "MacGoldenGate").lower()
    assert f"readonly property bool goldenGateEdition: {golden_gate}" in view.read_text()
    assert (widget / "contents/ui/MainView.qml").read_bytes() == original_view


@pytest.mark.parametrize("raw", ["{}", "[]", "{", '{"launcher_preset":true}',
                                 '{"launcher_preset":3}', '{"launcher_preset":"2"}'])
def test_invalid_edition_preset_falls_back_to_tahoe(tmp_path, monkeypatch, raw):
    path = tmp_path / "defaults.json"
    path.write_text(raw)
    monkeypatch.setattr(launcher_defaults, "DEFAULTS_FILE", path)
    assert launcher_defaults.default_launcher_preset() == 1


@pytest.mark.parametrize("relative", [
    "layouts/mac-tahoe.js",
    "look-and-feel/MacTahoeLiquidKde-Light/contents/layouts/org.kde.plasma.desktop-layout.js",
    "look-and-feel/MacTahoeLiquidKde-Dark/contents/layouts/org.kde.plasma.desktop-layout.js",
])
@pytest.mark.parametrize("presets", [[1, 2], [2, 1], [0, None]])
@pytest.mark.parametrize("edition_preset", [None, 1, 2])
def test_panel_rebuild_preserves_explicit_presets_per_screen(repo, relative, presets, edition_preset):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required to execute Plasma layout scripts")
    script = (repo / "src/offline" / relative).read_text()
    if edition_preset is not None:
        script = f"var mttkdeLauncherPreset = {edition_preset};\n" + script
    harness = r'''
const assert = require('node:assert/strict');
const saved = PRESETS;
const created = [];
const screenCount = 2;
function makeWidget(type, preset) {
    return { type, currentConfigGroup: [], config: {launcherPreset: preset},
        readConfig: function(key, fallback) { return this.config[key] ?? fallback; },
        writeConfig: function(key, value) { this.config[key] = value; } };
}
const existing = saved.map((preset, screen) => {
    const launcher = makeWidget('org.kde.mac-tahoe-liquid-kde.launcher', preset);
    return {screen, widgetIds: [100 + screen],
        widgetById: function() { return launcher; },
        remove: function() { launcher.config = {}; } };
});
function panels() { return existing; }
function userDataPath(type) { return "/home/tester/Downloads"; }
function applicationExists(id) { return false; }
function Panel() {
    this.items = [];
    this.addWidget = function(type) { const item = makeWidget(type); this.items.push(item); return item; };
    created.push(this);
}
'''.replace("PRESETS", json.dumps(presets))
    assertions = r'''
const docks = created.filter(p => p.location === 'bottom');
assert.ok(docks.length);
for (const dock of docks) {
    const launcher = dock.items.find(w => w.type === 'org.kde.mac-tahoe-liquid-kde.launcher');
    const expected = EDITION ?? saved[dock.screen];
    assert.equal(launcher.config.launcherPreset, expected === 1 || expected === 2 ? expected : undefined);
}
'''.replace("EDITION", json.dumps(edition_preset))
    result = subprocess.run([node, "-e", harness + script + assertions],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr



def test_native_launcher_anchor_geometry(repo, tmp_path, launcher_popup_module):
    """Late item layout must recenter the popup without a window resize."""
    if not shutil.which("Xvfb"):
        pytest.skip("Xvfb required for isolated native window positioning")
    with tempfile.TemporaryDirectory(prefix="launcher-anchor-") as runtime:
        env = os.environ | {
            "HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_DATA_HOME": str(tmp_path / "data"), "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_RUNTIME_DIR": runtime,
            "XDG_CONFIG_DIRS": "/etc/xdg", "XDG_DATA_DIRS": "/usr/local/share:/usr/share",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + runtime + "/no-host-bus",
            "QT_QPA_PLATFORM": "xcb", "QT_QPA_PLATFORMTHEME": "generic",
            "QT_QUICK_BACKEND": "software", "QT_FORCE_STDERR_LOGGING": "1",
            "QML_IMPORT_PATH": str(launcher_popup_module), "QT_SCALE_FACTOR": "1",
        }
        env.pop("WAYLAND_DISPLAY", None)
        read_fd, write_fd = os.pipe()
        server = subprocess.Popen(
            ["Xvfb", "-displayfd", str(write_fd), "-screen", "0", "1280x1024x24", "-nolisten", "tcp"],
            pass_fds=(write_fd,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        os.close(write_fd)
        try:
            assert select.select([read_fd], [], [], 10)[0], "Xvfb did not start"
            env["DISPLAY"] = ":" + os.read(read_fd, 32).decode().strip()
            result = subprocess.run(
                [str(launcher_popup_module.parent / "dockgeometryprobe"),
                 str(repo / "tests/qml/LauncherAnchorProbe.qml")],
                env=env, capture_output=True, text=True, timeout=15,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            assert "ANCHOR_OK" in result.stdout + result.stderr
        finally:
            os.close(read_fd)
            server.terminate()
            server.wait(timeout=5)



@pytest.mark.parametrize("scale", [1, 1.5])
def test_native_launcher_multiscreen_geometry(repo, tmp_path, launcher_popup_module, scale):
    """Exercise the native placement path without requiring a GPU/compositor."""
    screens = tmp_path / "screens.json"
    screens.write_text(json.dumps({"windowFrameMargins": False, "screens": [
        {"name": "first", "x": 0, "y": 0, "width": 1920, "height": 1440, "dpr": scale},
        {"name": "second", "x": 1920, "y": 0, "width": 1920, "height": 1440, "dpr": scale},
    ]}))
    with tempfile.TemporaryDirectory(prefix="launcher-geometry-") as runtime:
        env = os.environ | {
            "HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_DATA_HOME": str(tmp_path / "data"), "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_RUNTIME_DIR": runtime,
            "XDG_CONFIG_DIRS": "/etc/xdg", "XDG_DATA_DIRS": "/usr/local/share:/usr/share",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + runtime + "/no-host-bus",
            "QT_QPA_PLATFORM": "offscreen:configfile=" + str(screens),
            "QT_QPA_OFFSCREEN_NO_GLX": "1", "QT_QPA_PLATFORMTHEME": "generic",
            "QT_QUICK_BACKEND": "software", "QT_FORCE_STDERR_LOGGING": "1",
            "QML_IMPORT_PATH": str(launcher_popup_module), "QT_SCALE_FACTOR": "1",
        }
        for key in ("DISPLAY", "WAYLAND_DISPLAY"):
            env.pop(key, None)
        result = subprocess.run([
            str(launcher_popup_module.parent / "dockgeometryprobe"),
            str(repo / "tests/qml/LauncherScreensProbe.qml")],
            env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "LAUNCHER_SCREENS_OK" in result.stderr


@pytest.mark.parametrize("scale", [1, 1.5])
def test_native_launcher_reopens_on_another_screen(repo, tmp_path, launcher_popup_module, scale):
    """The cached parent still has its old QScreen when the capsule opens."""
    # KWin's virtual backend requires a DRM device; normal CI containers have
    # none. Keep the same native scenario mandatory through Qt's offscreen QPA
    # below, and qualify actual Wayland rendering in the disposable Plasma VM.
    if not any(os.access(node, os.R_OK | os.W_OK) for node in Path("/dev/dri").glob("renderD*")):
        pytest.skip("Live Wayland requires a DRM render node; native offscreen geometry remains covered")
    for tool in ("kwin_wayland", "dbus-run-session"):
        if not shutil.which(tool):
            pytest.skip(f"{tool} required for isolated multi-output Wayland")
    with tempfile.TemporaryDirectory(prefix="launcher-screens-") as runtime:
        env = os.environ | {
            "HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_DATA_HOME": str(tmp_path / "data"), "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_RUNTIME_DIR": runtime,
            "XDG_CONFIG_DIRS": "/etc/xdg", "XDG_DATA_DIRS": "/usr/local/share:/usr/share",
            "QT_QPA_PLATFORM": "offscreen", "QT_QPA_PLATFORMTHEME": "generic",
            "QT_QUICK_BACKEND": "software", "QT_FORCE_STDERR_LOGGING": "1",
            "QT_LOGGING_RULES": "*.debug=false;*.warning=true;*.critical=true",
            "QML_IMPORT_PATH": str(launcher_popup_module), "QT_SCALE_FACTOR": "1",
            "LIBGL_ALWAYS_SOFTWARE": "1", "KWIN_COMPOSE": "O2",
            # Match plasmashell's setup: Plasma owns absolute window placement.
            "QT_WAYLAND_DISABLE_FIXED_POSITIONS": "1",
        }
        for key in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS"):
            env.pop(key, None)
        bus = tmp_path / "screens-bus.conf"
        bus.write_text('<busconfig><type>session</type><listen>unix:tmpdir=/tmp</listen>'
                       '<policy context="default"><allow user="*"/><allow send_destination="*"/>'
                       '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        # copyfile omits system CAP_SYS_NICE xattrs rejected by containers.
        compositor = tmp_path / "kwin_wayland"
        shutil.copyfile(shutil.which("kwin_wayland"), compositor)
        compositor.chmod(0o755)
        client = tmp_path / "screens-client.sh"
        import shlex
        client.write_text("#!/bin/sh\nexport QT_QPA_PLATFORM=wayland\nexec " + shlex.join([
            str(launcher_popup_module.parent / "dockgeometryprobe"),
            str(repo / "tests/qml/LauncherScreensProbe.qml")]) + "\n")
        client.chmod(0o700)
        log_path = tmp_path / "screens.log"
        with log_path.open("w") as log:
            process = subprocess.Popen([
                "dbus-run-session", "--config-file", str(bus), "--", str(compositor),
                "--virtual", "--socket", "launcher-screens", "--width", "1920", "--height", "1440",
                "--scale", str(scale), "--output-count", "2", "--no-lockscreen",
                "--no-global-shortcuts", "--exit-with-session", str(client)],
                env=env, stdout=log, stderr=log, start_new_session=True)
            try:
                process.wait(timeout=30)
            finally:
                # KWin may leave a session helper alive after the client exits.
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
        output = log_path.read_text()
        assert process.returncode == 0, output[-6000:]
        assert "LAUNCHER_SCREENS_OK" in output, output[-6000:]
        assert "LAUNCHER_SCREENS_FAILED" not in output, output[-6000:]

@pytest.mark.parametrize("preset", [1, 2])
@pytest.mark.parametrize("mode", ["Light", "Dark"])
@pytest.mark.parametrize("edition", ["MacTahoe", "MacGoldenGate"])
def test_native_launcher_popup_presets(repo, tmp_path, monkeypatch, launcher_popup_module, preset, mode, edition, clipboard_daemon=None):
    for tool in ("plasmoidviewer", "Xvfb", "dbus-run-session", "xprop"):
        if not shutil.which(tool):
            pytest.skip(f"{tool} required for the isolated launcher preview")
    package = tmp_path / "widget"
    shutil.copytree(repo / "src/offline/plasmoids" / launcher_defaults.LAUNCHER_ID, package)
    shared = "org.kde.mac-tahoe-liquid-kde.controlcenter/contents/ui"
    destination = tmp_path / shared
    destination.mkdir(parents=True)
    for filename in ("MacOptionsMenu.qml", "NotificationContrast.js"):
        shutil.copy2(repo / "src/offline/plasmoids" / shared / filename, destination)
    shutil.copytree(repo / f"src/offline/plasma-theme/MacTahoeLiquidKde-{mode}",
                    tmp_path / f"data/plasma/desktoptheme/MacTahoeLiquidKde-{mode}")
    # Minimal CI desktops have no visible apps. Seed a real All Apps category
    # so the favorites-header assertions do not depend on the host's inventory.
    applications = tmp_path / "data/applications"
    applications.mkdir()
    for index in range(9):
        (applications / f"launcher-probe-{index}.desktop").write_text(
            "[Desktop Entry]\nType=Application\n"
            f"Name=Launcher Probe {index}\nExec=/bin/true\n"
            "Icon=application-x-executable\nCategories=Utility;\n"
        )
    (tmp_path / "config").mkdir()
    (tmp_path / "config/plasmarc").write_text(f"[Theme]\nname=MacTahoeLiquidKde-{mode}\n")
    shutil.copy2(repo / f"src/offline/color-schemes/MacTahoeLiquidKde{mode}.colors",
                 tmp_path / "config/kdeglobals")
    monkeypatch.setattr(launcher_defaults, "default_launcher_preset", lambda: preset)
    defaults = tmp_path / "defaults.json"
    defaults.write_text(json.dumps({"wallpaper": edition}))
    monkeypatch.setattr(launcher_defaults, "DEFAULTS_FILE", defaults)
    launcher_defaults.apply_launcher_default(package)
    ui = package / "contents/ui"
    entry = ui / "main.qml"
    entry.write_text(entry.read_text().replace(
        "mergeResults: true", 'mergeResults: true\n        runners: ["services"]', 1))
    # More favorites than columns exercise the single-row reference layout.
    favorites = '\n'.join(
        f'ListElement {{ display: "Favorite {i}"; name: "Favorite {i}"; '
        'decoration: "application-x-executable"; favoriteId: "test"; '
        'hasActionList: false }' for i in range(9))
    entry.write_text(entry.read_text().replace(
        'property QtObject globalFavorites: rootModel.favoritesModel',
        'property QtObject globalFavorites: ListModel { '
        'property var favorites: []; function trigger(index, action, argument) {}\n'
        + favorites + '\n}', 1))
    shutil.copy2(repo / ("tests/qml/ClipboardLauncherProbe.qml" if clipboard_daemon else "tests/qml/LauncherPresetProbe.qml"), ui)
    main = ui / "MainView.qml"
    source = main.read_text()
    end = source.rfind("}")
    golden_gate = str(edition == "MacGoldenGate").lower()
    dark = str(mode == "Dark").lower()
    event_loop_delay = 450 if os.environ.get("MTTKDE_TEST_LAUNCHER_SCALE") else 0
    if clipboard_daemon:
        main.write_text(source[:end] + "ClipboardLauncherProbe {}\n" + source[end:])
    else:
        main.write_text(source[:end] + f"LauncherPresetProbe {{ expectedPreset: {preset}; "
                        f"expectedGoldenGate: {golden_gate}; expectedDark: {dark}; eventLoopDelay: {event_loop_delay} }}\n" + source[end:])
    for name, original, replacement in (
        ("AllAppsList.qml", "ColumnLayout {", "ColumnLayout { property alias testCategories: categorySwitcher"),
        ("AppCategorySwitcher.qml", "Item {", "Item { property alias testView: categorySwitcher"),
        ("AppGridViewDelegate.qml", "Item {", "Item { property alias testActionMenu: actionMenu"),
        ("MenuButton.qml", "Item {", "Item { readonly property var testMenu: activeMenu; property alias testButton: button"),
        ("SearchBar.qml", "RowLayout {", "RowLayout { property alias testMenuButton: menuButton"),
        ("CategoryPill.qml", "Item {", "Item { property alias testBackground: pillBg"),
    ):
        path = ui / name
        path.write_text(path.read_text().replace(original, replacement, 1))

    # Keep KIO's Unix socket paths below the kernel's length limit.
    runtime = tempfile.TemporaryDirectory(prefix="launcher-runtime-")
    bus_config = tmp_path / "bus.conf"
    # No activation directories: tests cannot launch host desktop services.
    bus_config.write_text(
        '<busconfig><type>session</type><listen>unix:tmpdir=/tmp</listen>'
        '<policy context="default"><allow user="*"/><allow send_destination="*"/>'
        '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>'
    )
    env = os.environ | {
        "HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_DATA_HOME": str(tmp_path / "data"), "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_RUNTIME_DIR": runtime.name,
        "XDG_CONFIG_DIRS": "/etc/xdg", "XDG_DATA_DIRS": "/usr/local/share:/usr/share",
        "XDG_MENU_PREFIX": "plasma-",
        "QT_QPA_PLATFORM": "xcb", "QT_QPA_PLATFORMTHEME": "generic",
        "QT_QUICK_BACKEND": "software", "QT_FORCE_STDERR_LOGGING": "1",
        "QT_SCALE_FACTOR": os.environ.get("MTTKDE_TEST_LAUNCHER_SCALE", "1"),
        "QML_IMPORT_PATH": str(launcher_popup_module),
        "QT_LOGGING_RULES": "*.warning=true;*.critical=true",
        "XDG_SESSION_TYPE": "x11", "XDG_CURRENT_DESKTOP": "",
    }
    for key in ("DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY"):
        env.pop(key, None)
    read_fd, write_fd = os.pipe()
    scale = float(env["QT_SCALE_FACTOR"])
    screen_size = f"{round(1280 * scale)}x{round(1024 * scale)}x24"
    server = subprocess.Popen(
        ["Xvfb", "-displayfd", str(write_fd), "-screen", "0", screen_size, "-nolisten", "tcp"],
        pass_fds=(write_fd,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    os.close(write_fd)
    process = None
    log_path = tmp_path / "launcher.log"
    try:
        assert select.select([read_fd], [], [], 10)[0], "Xvfb did not start"
        env["DISPLAY"] = ":" + os.read(read_fd, 32).decode().strip()
        with log_path.open("w") as log:
            process = subprocess.Popen(
                ["dbus-run-session", "--config-file", str(bus_config), "--",
                 *([sys.executable, str(repo / "tests/native/clipboard_launcher_session.py"), str(clipboard_daemon)] if clipboard_daemon else []),
                 "plasmoidviewer", "-a", str(package), "-f", "horizontal", "-l", "bottomedge",
                 "--size", "1280x1024"],
                env=env, stdout=log, stderr=log, start_new_session=True,
            )
            deadline = time.monotonic() + 20
            popup_roles = {}
            while time.monotonic() < deadline:
                output = log_path.read_text()
                if "PROBE_PHASE 2 " in output:
                    for name in ("app", "search"):
                        if name not in popup_roles:
                            role = subprocess.run(
                                ["xprop", "-name", f"Launcher {name} role probe", "_NET_WM_WINDOW_TYPE"],
                                env=env, capture_output=True, text=True, timeout=5)
                            if role.returncode == 0:
                                popup_roles[name] = role.stdout
                if "LAUNCHER_PROBE_" in output or "CLIPBOARD_LAUNCHER_" in output or process.poll() is not None:
                    break
                time.sleep(0.05)
        output = log_path.read_text()
        if clipboard_daemon:
            assert "CLIPBOARD_LAUNCHER_OK" in output, output
            assert "CLIPBOARD_LAUNCHER_FAILED" not in output, output
            return
        assert "LAUNCHER_PROBE_OK" in output, output
        assert "LAUNCHER_PROBE_FAILED" not in output, output
        assert "_KDE_NET_WM_WINDOW_TYPE_APPLET_POPUP" in popup_roles.get("search", ""), popup_roles
        assert any(role in popup_roles.get("app", "") for role in (
            "_NET_WM_WINDOW_TYPE_DIALOG", "_KDE_NET_WM_WINDOW_TYPE_APPLET_POPUP")), popup_roles
        assert "_NET_WM_WINDOW_TYPE_DOCK" not in popup_roles["app"], popup_roles
    finally:
        os.close(read_fd)
        if process:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
        server.terminate()
        server.wait(timeout=5)
        runtime.cleanup()


@pytest.mark.parametrize("edition,mode,preset", [("MacTahoe", "Light", 1), ("MacGoldenGate", "Dark", 2)])
def test_native_launcher_fractional_scale(repo, tmp_path, monkeypatch, launcher_popup_module,
                                        edition, mode, preset):
    monkeypatch.setenv("MTTKDE_TEST_LAUNCHER_SCALE", "1.5")
    test_native_launcher_popup_presets(repo, tmp_path, monkeypatch, launcher_popup_module,
                                      preset, mode, edition)


def test_dock_applets_follow_panel_thickness(repo, tmp_path, launcher_popup_module):
    widgets = repo / 'src/offline/plasmoids'
    applets = ['launcher', 'trashcan']
    if (widgets / 'org.kde.mac-tahoe-liquid-kde.downloads').is_dir():
        applets.append('downloads')
    for widget in applets:
        source = (widgets / f'org.kde.mac-tahoe-liquid-kde.{widget}/contents/ui/main.qml').read_text()
        hints = re.findall(r'^    Layout\.(?:fillWidth|fillHeight|minimumWidth|preferredWidth|maximumWidth|minimumHeight|preferredHeight|maximumHeight):.*$', source, re.MULTILINE)
        # The Trash cell is wider by the room for the macOS separator before it.
        gap = re.search(r'^    readonly property int separatorGap: .*$', source, re.MULTILINE)
        hints = ([gap.group(0)] if gap else ['    readonly property int separatorGap: 0']) + hints
        assert hints, f'{widget} has no panel layout hints'
        assert 'Plasmoid.constraintHints: Plasmoid.CanFillArea' in source
        qml = """import QtQuick
import QtQuick.Layouts
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import org.kde.mac.tahoe.launcher as NativeLauncher
Item {
    id: root
    width: 600; height: 300
    QtObject { id: plasmoid; property int formFactor: PlasmaCore.Types.Horizontal; property var configuration: ({showSeparator:true}) }
    GridLayout {
        id: panel
        width: vertical ? 96 : 500
        height: vertical ? 500 : 96
        property bool vertical: false
        columns: vertical ? 1 : 2
        rows: vertical ? 2 : 1
        Item {
            id: applet
            NativeLauncher.DockCell { id: dockCell; applet: applet; vertical: panel.vertical }
            implicitWidth: 32; implicitHeight: 32
            property bool usesAppsPin: false
            HINTS
        }
        Item { Layout.fillWidth: true; Layout.fillHeight: true }
    }
    property int phase: 0
    property int settling: 0
    Timer {
        interval: 20; repeat: true; running: true
        onTriggered: {
            const thickness = panel.vertical ? panel.width : panel.height;
            const length = Math.max(16, Math.round(thickness * 13 / 17));
            if (Math.abs(applet.width - (panel.vertical ? thickness : length + applet.separatorGap)) > 0.01 || Math.abs(applet.height - (panel.vertical ? length : thickness)) > 0.01) {
                if (++root.settling < 10) return;
                console.error("DOCK_CELL_FAILED", root.phase, applet.width, applet.height, thickness);
                Qt.exit(1); return;
            }
            root.settling = 0;
            root.phase++;
            if (root.phase === 1) panel.height = 48;
            else if (root.phase === 2) panel.height = 128;
            else if (root.phase === 3) {
                plasmoid.formFactor = PlasmaCore.Types.Vertical;
                panel.vertical = true;
            } else if (root.phase === 4) panel.width = 32;
            else if (root.phase === 5) panel.width = 64;
            else { console.info("DOCK_CELL_OK"); Qt.exit(0); }
        }
    }
}
""".replace('HINTS', '\n'.join(hints).replace('Plasmoid.formFactor', 'plasmoid.formFactor'))
        path = tmp_path / f'{widget}.qml'
        path.write_text(qml)
        result = subprocess.run([str(launcher_popup_module.parent / 'dockgeometryprobe'), str(path)],
            env=dict(os.environ, QML_IMPORT_PATH=str(launcher_popup_module), QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                     QT_FORCE_STDERR_LOGGING='1'), capture_output=True, text=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'DOCK_CELL_OK' in result.stdout + result.stderr


@pytest.fixture(scope="session")
def dock_icon_theme(repo, tmp_path_factory):
    """Use real bundled artwork even in CI images with no default icon theme."""
    staging = tmp_path_factory.mktemp("dock-artwork")
    base = "MacTahoeLiquidKde-Icons"
    members = [f"{base}/places/{size}/{name}.svg"
               for size in ("16", "22", "24", "scalable")
               for name in ("user-trash", "user-trash-full")]
    members.append(f"{base}/apps/scalable/file-manager.svg")
    subprocess.run(["tar", "--zstd", "-xf",
                    str(repo / f"src/offline/icons/{base}.tar.zst"),
                    "-C", str(staging), *members], check=True, capture_output=True, timeout=30)
    theme = staging / "DockAlignmentTest"
    shutil.copytree(staging / base / "places", theme)
    shutil.copy2(staging / base / "apps/scalable/file-manager.svg", theme / "scalable/folder.svg")
    sections = ["[Icon Theme]", "Name=DockAlignmentTest", "Directories=16,22,24,scalable", ""]
    for size in (16, 22, 24):
        sections += [f"[{size}]", f"Size={size}", "Type=Fixed", "Context=Places", ""]
    sections += ["[scalable]", "Size=64", "Type=Scalable", "MinSize=32",
                 "MaxSize=512", "Context=Places", ""]
    (theme / "index.theme").write_text("\n".join(sections))
    return theme


@pytest.mark.parametrize("scale", [1, 1.25, 1.5, 1.75, 2, 2.5, 3])
def test_custom_dock_icons_share_task_frame_geometry(repo, tmp_path, launcher_popup_module, dock_icon_theme, scale):
    """Compare the shared applet icon with the actual task iconBox QML."""
    widgets = repo / 'src/offline/plasmoids'
    for relative in (
            'org.kde.mac-tahoe-liquid-kde.launcher/contents/ui/CompactRepresentation.qml',
            'org.kde.mac-tahoe-liquid-kde.trashcan/contents/ui/main.qml'):
        assert 'NativeLauncher.DockIcon {' in (widgets / relative).read_text()
    assert 'normalizeTrashArtwork: true' in (widgets /
        'org.kde.mac-tahoe-liquid-kde.trashcan/contents/ui/main.qml').read_text()
    downloads = widgets / 'org.kde.mac-tahoe-liquid-kde.downloads/contents/ui/main.qml'
    if downloads.is_file():
        assert 'NativeLauncher.DockIcon {' in downloads.read_text()
    runner = launcher_popup_module.parent / 'dockgeometryprobe'
    task = (repo / 'src/offline/plasmoids/org.kde.mac.tahoe.liquid.taskmanager/contents/ui/Task.qml').read_text()
    icon_box = task.split('    Loader {\n        id: iconBox', 1)[1].split('\n    PlasmaComponents3.Label {', 1)[0]
    # Execute the production delegate's complete icon box, including its
    # standalone state, margins and icon. Only its task-model inputs are faked.
    reference = '''import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.ksvg as KSvg
import org.kde.plasma.core as PlasmaCore
Item {
    id: task
    property alias iconItem: icon
    property int location: PlasmaCore.Types.BottomEdge
    property bool inPopup: false
    property var smartLauncherItem: null
    property bool highlighted: false
    property var model: ({IsStartup: false, decoration: "folder"})
    property var tasksRoot: task
    property bool iconsOnly: true
    property bool vertical: location === PlasmaCore.Types.LeftEdge || location === PlasmaCore.Types.RightEdge
    property var iconThemeWatcher: null
    Item { id: label; visible: false }
    Component { id: busyIndicator; Item {} }
    QtObject { id: backend; function iconSource(source) { return source; } }
    QtObject {
        id: layoutMetrics
        function horizontalMargins() { return taskFrame.margins.left + taskFrame.margins.right; }
        function verticalMargins() { return taskFrame.margins.top + taskFrame.margins.bottom; }
    }
    KSvg.FrameSvgItem {
        id: taskFrame
        visible: false
        imagePath: "widgets/tasks"
        prefix: {
            switch (task.location) {
            case PlasmaCore.Types.LeftEdge: return ["west-normal", "normal"];
            case PlasmaCore.Types.TopEdge: return ["north-normal", "normal"];
            case PlasmaCore.Types.RightEdge: return ["east-normal", "normal"];
            default: return ["south-normal", "normal"];
            }
        }
    }
    Loader {
        id: iconBox''' + icon_box.replace('LayoutMetrics.', 'layoutMetrics.') + '\n}\n'
    (tmp_path / 'ReferenceTaskIcon.qml').write_text(reference)
    probe = repo / 'tests/qml/DockAlignmentProbe.qml'
    shutil.copy2(probe, tmp_path / 'tst_dock.qml')
    for mode in ('Light', 'Dark'):
        data = tmp_path / mode / 'data'
        config = tmp_path / mode / 'config'
        config.mkdir(parents=True)
        (data / 'icons').mkdir(parents=True)
        shutil.copytree(dock_icon_theme, data / 'icons/DockAlignmentTest')
        theme = f'MacTahoeLiquidKde-{mode}'
        shutil.copytree(repo / f'src/offline/plasma-theme/{theme}', data / f'plasma/desktoptheme/{theme}')
        (config / 'plasmarc').write_text(f'[Theme]\nname={theme}\n')
        result = subprocess.run([str(runner), str(tmp_path / 'tst_dock.qml')],
            env=dict(os.environ, QML_IMPORT_PATH=str(launcher_popup_module), QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                     QT_FORCE_STDERR_LOGGING='1', QT_SCALE_FACTOR=str(scale),
                     DOCK_ICON_THEME='DockAlignmentTest',
                     QT_SCALE_FACTOR_ROUNDING_POLICY='PassThrough', XDG_CONFIG_HOME=str(config),
                     XDG_DATA_HOME=str(data)),
            capture_output=True, text=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'DOCK_ALIGNMENT_OK' in result.stdout + result.stderr
        assert f'DOCK_DPR: {scale:g}' in result.stdout + result.stderr


@pytest.mark.parametrize("scale", [1, 1.25, 1.5, 1.75, 2, 2.5, 3])
def test_dock_boundary_spacing(repo, tmp_path, launcher_popup_module, scale):
    """Production task metrics/grid keep every boundary on the same pitch."""
    ui = repo / 'src/offline/plasmoids/org.kde.mac.tahoe.liquid.taskmanager/contents/ui'
    shutil.copy2(ui / 'LayoutMetrics.js', tmp_path)
    grid = (ui / 'TaskList.qml').read_text().replace(
        'Plasmoid.formFactor === PlasmaCore.Types.Vertical', 'tasks.vertical').replace(
            'Plasmoid.configuration', 'tasks.plasmoid.configuration')
    (tmp_path / 'TaskList.qml').write_text(grid)
    main = (ui / 'main.qml').read_text()
    width_sum = re.search(r'Layout.maximumWidth: \{(.*?)\n                \}', main, re.S).group(1)
    height_sum = re.search(r'Layout.maximumHeight: \{(.*?)\n                \}', main, re.S).group(1)
    qml = """import QtQuick
import QtQuick.Layouts
import org.kde.plasma.core as PlasmaCore
import org.kde.ksvg as KSvg
import org.kde.kirigami as Kirigami
import "LayoutMetrics.js" as LayoutMetrics
Item {
    id: tasks
    width: 68; height: 68
    property bool vertical: false
    property bool iconsOnly: true
    property var plasmoid: ({pluginName: "org.kde.mac.tahoe.liquid.icontasks",
        configuration: {iconSpacing: 1, maxStripes: 1, forceStripes: false}})
    KSvg.FrameSvgItem { id: taskFrame; imagePath: "widgets/tasks"; prefix: ["south-normal", "normal"]; visible: false }
    TaskList {
        id: taskList
        count: 3
        readonly property real widthOccupation: count / columns
        readonly property real heightOccupation: count / rows
        Layout.maximumWidth: { WIDTH_SUM }
        Layout.maximumHeight: { HEIGHT_SUM }
        width: tasks.vertical ? tasks.width : Layout.maximumWidth
        height: tasks.vertical ? Layout.maximumHeight : tasks.height
        Repeater {
            model: 3
            Item {
                Layout.fillWidth: true; Layout.fillHeight: true
                Layout.maximumWidth: tasks.vertical ? -1 : LayoutMetrics.preferredMaxWidth()
                Layout.maximumHeight: tasks.vertical ? LayoutMetrics.preferredMaxHeight() : -1
                implicitWidth: tasks.width; implicitHeight: tasks.height
            }
        }
    }
    property int phase: 0
    readonly property var sizes: [40, 48, 68, 96, 128, 68, 40]
    function compare(a,b) { if (Math.abs(a-b)>0.05) throw new Error(a+" != "+b); }
    Timer {
        interval: 20; repeat: true; running: true
        onTriggered: {
            try {
                const cells = taskList.children.filter(c => c.width > 0 && c.height > 0);
                const t = Math.max(16, Math.round((tasks.vertical ? tasks.width : tasks.height) * 13 / 17));
                const a = tasks.vertical ? "y" : "x";
                const length = tasks.vertical ? "height" : "width";
                const pitch = cells[1][a] - cells[0][a];
                // Native panel inserts smallSpacing between standalone applets.
                compare(pitch, t + Kirigami.Units.smallSpacing);
                compare(cells[0][length], t);
                compare(cells[2][a] - cells[1][a], pitch);
                // Launcher -> first task; last task -> Downloads -> Trash.
                compare(t/2 + Kirigami.Units.smallSpacing + cells[0][a] + cells[0][length]/2, pitch);
                compare(taskList[length] - cells[2][a] - cells[2][length]/2
                        + Kirigami.Units.smallSpacing + t/2, pitch);
                compare(t + Kirigami.Units.smallSpacing, pitch);
                tasks.plasmoid = {pluginName: "org.kde.mac.tahoe.liquid.icontasks",
                    configuration: {iconSpacing: [0, 1, 3][tasks.phase % 3], maxStripes: 1, forceStripes: false}};
                tasks.phase++;
                if (tasks.phase === sizes.length * 2) { console.info("DOCK_GAPS_OK"); Qt.exit(0); return; }
                tasks.vertical = tasks.phase >= sizes.length;
                tasks.width = sizes[tasks.phase % sizes.length]; tasks.height = tasks.width;
            } catch (e) { console.error("DOCK_GAPS_FAILED", tasks.phase, e); Qt.exit(1); }
        }
    }
}
""".replace('WIDTH_SUM', width_sum).replace('HEIGHT_SUM', height_sum)
    path = tmp_path / 'DockGaps.qml'
    path.write_text(qml)
    result = subprocess.run([str(launcher_popup_module.parent / 'dockgeometryprobe'), str(path)],
        env=dict(os.environ, QML_IMPORT_PATH=str(launcher_popup_module), QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                 QT_SCALE_FACTOR=str(scale), QT_FORCE_STDERR_LOGGING='1'),
        capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'DOCK_GAPS_OK' in result.stdout + result.stderr


def test_dock_separator_upgrade_preserves_pins_and_other_widgets(repo, tmp_path, launcher_popup_module):
    script = (repo / 'src/offline/layouts/dock-spacing.js').read_text()
    qml = '''import QtQuick
Item {
    property var removed: []
    property var dock: []
    property var topWidgets: []
    function widget(type, id) { return {type: type, id: id, index: id, remove: function() { removed.push(id); }}; }
    function panels() { return [{widgets: function() { return dock.filter(w => removed.indexOf(w.id)<0); }},
                               {widgets: function() { return topWidgets; }}]; }
    function migrate() { SCRIPT }
    Timer { interval: 1; running: true; onTriggered: {
        const launcher = "org.kde.mac-tahoe-liquid-kde.launcher";
        const tasks = "org.kde.mac.tahoe.liquid.icontasks";
        const trash = "org.kde.mac-tahoe-liquid-kde.trashcan";
        const downloads = "org.kde.mac-tahoe-liquid-kde.downloads";
        const separator = "org.kde.plasma.marginsseparator";
        dock = [widget(launcher, 1), widget(separator, 2), widget(tasks, 3),
                widget(separator, 4), widget(downloads, 5), widget(trash, 6),
                widget(separator, 7), widget("org.kde.plasma.digitalclock", 8)];
        const pinned = dock[2];
        pinned.pins = ["applications:org.kde.kate.desktop"];
        // Widget enumeration follows creation order, not current panel order.
        dock = [dock[0], dock[2], dock[4], dock[5], dock[1], dock[3], dock[6], dock[7]];
        topWidgets = [widget("org.kde.plasma.systemtray", 10), widget(separator, 11),
               widget("org.kde.plasma.digitalclock", 12)];
        migrate(); migrate();
        if (JSON.stringify(removed)!=="[2,4]" || pinned.pins[0]!=="applications:org.kde.kate.desktop") {
            console.error("DOCK_MIGRATION_FAILED", JSON.stringify(removed)); Qt.exit(1); return;
        }
        console.info("DOCK_MIGRATION_OK"); Qt.exit(0);
    }}
}'''.replace('SCRIPT', script)
    path = tmp_path / 'DockMigration.qml'
    path.write_text(qml)
    result = subprocess.run([str(launcher_popup_module.parent / 'dockgeometryprobe'), str(path)],
        env=dict(os.environ, QML_IMPORT_PATH=str(launcher_popup_module), QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                 QT_FORCE_STDERR_LOGGING='1'), capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'DOCK_MIGRATION_OK' in result.stdout + result.stderr



@pytest.mark.parametrize("scale", [1, 1.5, 2])
def test_dock_cells_share_compression_and_limit_extra_space(repo, tmp_path, launcher_popup_module, scale):
    ui = repo / 'src/offline/plasmoids/org.kde.mac.tahoe.liquid.taskmanager/contents/ui'
    shutil.copy2(ui / 'LayoutMetrics.js', tmp_path)
    (tmp_path / 'TaskList.qml').write_text((ui / 'TaskList.qml').read_text().replace(
        'Plasmoid.formFactor === PlasmaCore.Types.Vertical', 'tasks.vertical').replace(
        'Plasmoid.configuration', 'tasks.plasmoid.configuration'))
    main = (ui / 'main.qml').read_text()
    hints = []
    for key in ('minimumWidth', 'minimumHeight', 'preferredWidth', 'preferredHeight'):
        hints.append(re.search(r'^    Layout\.' + key + r': \{.*?^    \}', main, re.M | re.S).group(0))
    for key in ('maximumWidth', 'maximumHeight'):
        hints.append(re.search(r'^    Layout\.' + key + r':.*$', main, re.M).group(0))
    sums = [re.search(r'Layout\.' + key + r': \{(.*?)\n                \}', main, re.S).group(1)
            for key in ('maximumWidth', 'maximumHeight')]
    applet = (repo / 'src/offline/plasmoids/org.kde.mac-tahoe-liquid-kde.launcher/contents/ui/main.qml').read_text()
    applet_hints = re.findall(r'^    Layout\.(?:minimumWidth|preferredWidth|maximumWidth|minimumHeight|preferredHeight|maximumHeight):.*$', applet, re.M)
    applet_hints = '\n'.join(applet_hints).replace('Plasmoid.formFactor', 'plasmoid.formFactor')
    qml = """import QtQuick
import QtQuick.Layouts
import org.kde.plasma.core as PlasmaCore
import org.kde.ksvg as KSvg
import org.kde.kirigami as Kirigami
import org.kde.mac.tahoe.launcher as NativeLauncher
import "LayoutMetrics.js" as LayoutMetrics
Item {
    id: root
    width: 1200; height: 1200
    property bool vertical: false
    property int phase: 0
    property int taskCount: 10
    property int settling: 0
    property bool fit: false
    KSvg.FrameSvgItem { id: taskFrame; imagePath: "widgets/tasks"; prefix: ["south-normal", "normal"]; visible: false }
    QtObject { id: plasmoid; property int formFactor: root.vertical ? PlasmaCore.Types.Vertical : PlasmaCore.Types.Horizontal }
    component DockApplet: Item {
        id: cell
        readonly property bool usesAppsPin: false // This fixture measures the standalone launcher cell.
        NativeLauncher.DockCell { id: dockCell; applet: cell; vertical: root.vertical }
        Layout.fillWidth: true; Layout.fillHeight: true
        APPLET_HINTS
    }
    GridLayout {
        id: panel
        width: root.vertical ? 68 : root.fit ? Layout.maximumWidth : available
        height: root.vertical ? available : 68
        property real available: 1100
        columns: root.vertical ? 1 : 5; rows: root.vertical ? 5 : 1
        rowSpacing: Kirigami.Units.smallSpacing; columnSpacing: rowSpacing
        DockApplet { id: launcher }
        Item {
            id: tasks
            property bool vertical: root.vertical
            property bool iconsOnly: true
            property bool shouldShrinkToZero: false
            property var plasmoid: ({pluginName: "org.kde.mac.tahoe.liquid.icontasks",
                configuration: {iconSpacing: 1, maxStripes: 1, forceStripes: false}})
            NativeLauncher.DockCell {
                applet: tasks; vertical: root.vertical; taskManager: true
                count: tasks.vertical ? taskList.rows : taskList.columns
                spacing: tasks.vertical ? taskList.rowSpacing : taskList.columnSpacing
            }
            Layout.fillWidth: true; Layout.fillHeight: true
            TASK_HINTS
            TaskList {
                id: taskList
                count: root.taskCount
                readonly property real widthOccupation: count / columns
                readonly property real heightOccupation: count / rows
                Layout.maximumWidth: { WIDTH_SUM }
                Layout.maximumHeight: { HEIGHT_SUM }
                width: tasks.width; height: tasks.height
                Repeater {
                    model: root.taskCount
                    Item {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        Layout.maximumWidth: tasks.vertical ? -1 : LayoutMetrics.preferredMaxWidth()
                        Layout.maximumHeight: tasks.vertical ? LayoutMetrics.preferredMaxHeight() : -1
                        implicitWidth: 16; implicitHeight: 16
                    }
                }
            }
        }
        DockApplet { id: downloads }
        DockApplet { id: trash }
        Item { visible: !root.fit; Layout.fillWidth: true; Layout.fillHeight: true }
    }
    function compare(a,b) { if (Math.abs(a-b)>1.1) throw new Error(a+" != "+b); }
    Timer { interval: 30; repeat: true; running: true; onTriggered: {
        try {
            const cells = taskList.children.filter(c => c.width>0 && c.height>0);
            if (cells.length !== root.taskCount) throw new Error("Task delegates are still updating");
            const pos = root.vertical ? "y" : "x", length = root.vertical ? "height" : "width";
            const pitch = cells.length > 1
                ? cells[1][pos] + cells[1][length]/2 - cells[0][pos] - cells[0][length]/2
                : cells[0][length] + Kirigami.Units.smallSpacing;
            compare(launcher[length], cells[0][length]);
            // A fit-content panel must recover its natural pitch after being
            // compressed or receiving a new SVG's geometry notification.
            if (root.fit) compare(cells[0][length], NativeLauncher.DockMetrics.preferredCellSize(68));
            if (downloads.visible) compare(downloads[length], cells[0][length]);
            compare(trash[length], cells[0][length]);
            compare(tasks[pos] + cells[0][pos] + cells[0][length]/2 - launcher[pos] - launcher[length]/2, pitch);
            const last = cells[cells.length - 1];
            const next = downloads.visible ? downloads : trash;
            compare(next[pos] + next[length]/2 - tasks[pos] - last[pos] - last[length]/2, pitch);
            if (downloads.visible) compare(trash[pos] + trash[length]/2 - downloads[pos] - downloads[length]/2, pitch);
            root.settling = 0;
            root.phase++;
            if (root.phase === 13) { console.info("DOCK_COMPRESS_OK"); Qt.exit(0); return; }
            root.vertical = root.phase >= 3 && root.phase < 6;
            panel.available = [1100, 650, 350][root.phase % 3];
            if (root.phase >= 6 && root.phase < 9) {
                root.taskCount = 3;
                downloads.visible = root.phase !== 7;
                panel.available = root.phase === 7 ? 180 : 350;
            }
            if (root.phase >= 9) {
                root.fit = true;
                root.taskCount = [14, 1, 20, 14][root.phase - 9];
                downloads.visible = root.phase !== 11;
            }
        } catch(e) {
            if (++root.settling < 10) return;
            console.error("DOCK_COMPRESS_FAILED", root.phase, e); Qt.exit(1);
        }
    }}
}
""".replace('APPLET_HINTS', applet_hints).replace('TASK_HINTS', '\n'.join(hints)).replace('WIDTH_SUM', sums[0]).replace('HEIGHT_SUM', sums[1])
    path = tmp_path / 'DockCompression.qml'
    path.write_text(qml)
    result = subprocess.run([str(launcher_popup_module.parent / 'dockgeometryprobe'), str(path)],
        env=dict(os.environ, QML_IMPORT_PATH=str(launcher_popup_module), QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                 QT_SCALE_FACTOR=str(scale), QT_FORCE_STDERR_LOGGING='1'), capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'DOCK_COMPRESS_OK' in result.stdout + result.stderr
    assert f'DOCK_DPR: {scale}' in result.stdout + result.stderr


def test_dock_spacing_is_not_configurable(repo):
    package = repo / 'src/offline/plasmoids/org.kde.mac.tahoe.liquid.taskmanager'
    for relative in ('contents/config/main.xml', 'contents/ui/ConfigAppearance.qml',
                     'contents/ui/LayoutMetrics.js'):
        assert 'iconSpacing' not in (package / relative).read_text()


def test_dock_hover_zoom_is_reduced_and_centered(repo, tmp_path, launcher_popup_module):
    """Execute production task transforms and shared end-icon rendering together."""
    task = (plasmoids.TASKMANAGER_SRC / 'contents/ui/Task.qml').read_text()
    transforms = task[task.index('    readonly property bool dockMagnified:'):task.index('    active: !inPopup')]
    qml = r'''import QtQuick
import org.kde.plasma.core as PlasmaCore
import org.kde.mac.tahoe.launcher as NativeLauncher
Item {
    id: root; width: 400; height: 100
    property int phase: 0
    property bool hovering: false
    property bool vertical: false
    property bool panel: true
    property bool popup: false
    property real amount: 110
    QtObject { id: tasksRoot; property bool vertical: root.vertical }
    QtObject { id: plasmoid; property QtObject configuration: QtObject { property real dockMagnification: root.amount } }
    Item {
        id: task; x: 130; y: 10; width: 52; height: 68
        property bool inPopup: root.popup
        property bool containsMouse: root.hovering
        TRANSFORMS
    }
    NativeLauncher.DockIcon {
        id: launcher; x: 30; y: 10; width: 52; height: 68
        source: "start-here-kde"; hovered: root.hovering; inPanel: root.panel
        location: root.vertical ? PlasmaCore.Types.LeftEdge : PlasmaCore.Types.BottomEdge
    }
    NativeLauncher.DockIcon {
        id: trash; x: 230; y: 10; width: 52; height: 68
        source: "user-trash"; normalizeTrashArtwork: true
        hovered: root.hovering; inPanel: root.panel
        location: launcher.location
    }
    function check(item, expected) {
        const center = item.mapToItem(root, item.width / 2, item.height / 2);
        const top = item.mapToItem(root, 0, 0);
        const bottom = item.mapToItem(root, item.width, item.height);
        if (Math.abs(item.scale - expected) > 0.0001
            || Math.abs(center.x - item.x - 26) > 0.001
            || Math.abs(center.y - item.y - 34) > 0.001
            || Math.abs(bottom.y - top.y - 68 * expected) > 0.001
            || item.width !== 52 || item.height !== 68) {
            console.error("ZOOM_FAILED", root.phase, item, item.scale, expected, center);
            Qt.exit(1); return false;
        }
        return true;
    }
    Timer {
        running: true; repeat: true; interval: 250
        onTriggered: {
            let taskScale = root.hovering && !root.vertical && !root.popup
                ? 1 + (Math.max(100, Math.min(150, root.amount)) / 100 - 1) * 0.9 : 1;
            let endScale = root.hovering && root.panel && !root.vertical ? 1.09 : 1;
            if (!root.check(task, taskScale) || !root.check(launcher, endScale) || !root.check(trash, endScale)) return;
            switch (++root.phase) {
            case 1: root.hovering = true; break;
            case 2: root.hovering = false; break;
            case 3: root.hovering = true; root.vertical = true; break;
            case 4: root.vertical = false; root.panel = false; root.popup = true; break;
            case 5: root.panel = true; root.popup = false; root.amount = 150; break;
            case 6: root.amount = 80; break;
            case 7: root.amount = 180; break;
            default: console.info("DOCK_ZOOM_OK"); Qt.exit(0);
            }
        }
    }
}
'''.replace('TRANSFORMS', transforms.replace('Plasmoid.configuration', 'plasmoid.configuration'))
    path = tmp_path / 'DockZoom.qml'
    path.write_text(qml)
    result = subprocess.run([str(launcher_popup_module.parent / 'dockgeometryprobe'), str(path)],
        env=dict(os.environ, QML_IMPORT_PATH=str(launcher_popup_module), QT_QPA_PLATFORM='offscreen',
                 QT_QUICK_BACKEND='software', QT_FORCE_STDERR_LOGGING='1'),
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'DOCK_ZOOM_OK' in result.stdout + result.stderr


@pytest.mark.parametrize("delegate", ["AppGridViewDelegate.qml", "AppListViewDelegate.qml"])
def test_launcher_icons_repaint_after_theme_change(repo, tmp_path, launcher_popup_module, delegate):
    for name, color in (("probe-light", "#ff0000"), ("probe-dark", "#0000ff")):
        directory = tmp_path / name / "32x32/apps"
        directory.mkdir(parents=True)
        (directory.parent.parent / "index.theme").write_text(
            f"[Icon Theme]\nName={name}\nDirectories=32x32/apps\n"
            "[32x32/apps]\nSize=32\nType=Fixed\nContext=Applications\n")
        (directory / "launcher-test.svg").write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">'
            f'<rect width="32" height="32" fill="{color}"/></svg>')
    source = (repo / "src/offline/plasmoids" / launcher_defaults.LAUNCHER_ID / "contents/ui" / delegate).read_text()
    start = source.index("Kirigami.Icon {")
    end = start + len("Kirigami.Icon {")
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    icon_id = "appicon" if delegate.startswith("AppGrid") else "icon"
    qml = tmp_path / "icon-theme.qml"
    qml.write_text('''import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.mac.tahoe.launcher as NativeLauncher
import LauncherInteraction 1.0
Item {
    id: root
    width: 100; height: 100
    property int iconSize: 32
    property bool compact: false
    QtObject { id: model; property string decoration: "launcher-test" }
    QtObject {
        id: main
        property bool detachedSearch: true
        property bool tahoeStyle: false
        property QtObject iconThemeWatcher: NativeLauncher.IconThemeWatcher {}
    }
    ICON_BODY
    Timer {
        interval: 100; running: true; repeat: true
        property int phase: 0
        onTriggered: {
            const directory = DIRECTORY;
            if (phase > 0) {
                const actual = LauncherInteraction.pixel(ICON_ID);
                const expected = phase === 2 ? "#0000ff" : "#ff0000";
                if (actual.toString() !== expected) {
                    console.error("ICON_REPAINT_FAILED", phase, actual); Qt.exit(1); return;
                }
            }
            if (phase === 3) { console.info("ICON_REPAINT_OK"); Qt.exit(0); return; }
            LauncherInteraction.setIconTheme(directory, phase === 1 ? "probe-dark" : "probe-light");
            main.iconThemeWatcher.changed();
            phase++;
        }
    }
}
'''.replace("ICON_BODY", source[start:end]).replace("ICON_ID", icon_id)
        .replace("DIRECTORY", json.dumps(str(tmp_path))))
    result = subprocess.run([str(launcher_popup_module.parent / "dockgeometryprobe"), str(qml)],
        env=dict(os.environ, QML_IMPORT_PATH=str(launcher_popup_module), QT_QPA_PLATFORM="offscreen",
                 QT_QPA_PLATFORMTHEME="generic", QT_QUICK_BACKEND="software", QT_FORCE_STDERR_LOGGING="1"),
        capture_output=True, text=True, timeout=15)
    assert result.returncode == 0 and "ICON_REPAINT_OK" in result.stderr, result.stdout + result.stderr


@pytest.fixture(scope="session")
def clipboard_launcher_daemon(repo, tmp_path_factory):
    build = tmp_path_factory.mktemp("clipboard-launcher-daemon")
    for command in (["cmake", "-S", str(repo / "src/offline/clipboard/clipd"), "-B", str(build)],
                    ["cmake", "--build", str(build), "-j2"]):
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
    return build / "mac-tahoe-clipd"


@pytest.mark.parametrize("edition,mode,preset", [("MacTahoe", "Light", 1), ("MacGoldenGate", "Dark", 2)])
def test_clipboard_launcher_integration(repo, tmp_path, monkeypatch, launcher_popup_module,
                                       clipboard_launcher_daemon, edition, mode, preset):
    pytest.importorskip("PyQt6.QtDBus")
    test_native_launcher_popup_presets(repo, tmp_path, monkeypatch, launcher_popup_module,
                                      preset, mode, edition, clipboard_launcher_daemon)
@pytest.mark.parametrize("scale", [1, 1.45])
def test_control_center_glass_regions(launcher_popup_module, scale):
    """Floating controls blur and receive input only inside their rounded islands."""
    result = subprocess.run(
        [str(launcher_popup_module.parent / 'controlglassprobe')],
        env=dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_SCALE_FACTOR=str(scale),
                 DBUS_SESSION_BUS_ADDRESS='unix:path=/tmp/no-control-glass-test-bus'),
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'CONTROL_GLASS_REGIONS_OK' in result.stdout


def test_control_center_native_x11_render(repo, tmp_path, launcher_popup_module):
    """The original QML layout and native input mask agree on an isolated display."""
    if not shutil.which('Xvfb'):
        pytest.skip('Xvfb required for native Control Center rendering')
    runtime = tmp_path / 'runtime'; runtime.mkdir(mode=0o700)
    bus_config = runtime / 'bus.conf'
    bus_config.write_text('<busconfig><type>session</type><listen>unix:tmpdir=' + str(runtime)
                         + '</listen><auth>EXTERNAL</auth><policy context="default">'
                         + '<allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
    env = os.environ | {
        'HOME': str(tmp_path), 'XDG_RUNTIME_DIR': str(runtime),
        'XDG_CONFIG_HOME': str(tmp_path / 'config'), 'XDG_DATA_HOME': str(tmp_path / 'data'),
        'XDG_CACHE_HOME': str(tmp_path / 'cache'), 'QT_QPA_PLATFORM': 'xcb',
        'QT_QPA_PLATFORMTHEME': 'generic', 'QT_QUICK_BACKEND': 'software',
        'DBUS_SYSTEM_BUS_ADDRESS': 'unix:path=' + str(runtime / 'no-system-bus'),
        'PULSE_SERVER': 'unix:' + str(runtime / 'no-audio'),
        'QML_IMPORT_PATH': str(launcher_popup_module),
    }
    env.pop('WAYLAND_DISPLAY', None)
    read_fd, write_fd = os.pipe()
    server = subprocess.Popen(
        ['Xvfb', '-displayfd', str(write_fd), '-screen', '0', '1280x1024x24', '-nolisten', 'tcp'],
        pass_fds=(write_fd,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.close(write_fd)
    try:
        assert select.select([read_fd], [], [], 10)[0], 'Xvfb did not start'
        env['DISPLAY'] = ':' + os.read(read_fd,32).decode().strip()
        result = subprocess.run(
            ['dbus-run-session', '--config-file', str(bus_config), '--', sys.executable, str(repo / 'tests/desktop_controls_render.py'),
             str(repo), str(tmp_path / 'control-center.png')],
            env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'CONTROL_CENTER_X11_RENDER_OK' in result.stdout
    finally:
        os.close(read_fd);server.terminate();server.wait(timeout=5)
