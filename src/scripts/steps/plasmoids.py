from localization import tr
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from distro import qt6_plugins_dir, qt6_qml_dir
from installer_choices import selected
from utils import qdbus_cmd, run_user
from launcher_defaults import LAUNCHER_ID, apply_launcher_default, remember_installed_edition
from steps._native_build import cmake_build
from steps._helpers import (
    DATA_HOME, HOME, build_dir, fail, info, install_tree, ok, offline,
    remove_tree, qdbus_call, warn,
    sudo_install_file, sudo_install_tree, sudo_remove, temp_dir,
)

SRC_DIR = offline("plasmoids")
DEST_DIR = DATA_HOME / "plasma/plasmoids"
WIDGETS_ARCHIVE = offline("desktop-widgets", "liquidglass-kde-widgets.tar.zst")
WIDGETS_STATE = DATA_HOME / "mac-tahoe-liquid-kde/desktop-widgets.list"
WIDGET_ID = re.compile(r"com\.jaxparrow07\.macoswidgets\.[a-z0-9-]+")
DESKTOP_STARTERS = tuple("com.jaxparrow07.macoswidgets." + name
                         for name in ("calendar", "clock-analog", "timer"))

TASKMANAGER_SRC = SRC_DIR / "org.kde.mac.tahoe.liquid.taskmanager"
TASKMANAGER_BUILD = build_dir("plasmoids/org.kde.mac.tahoe.liquid.taskmanager")
# Qt6 never scans user paths for plugins/QML — these go under the qmake6-
# reported libdir. Lazy __getattr__ keeps a missing qmake6 a preflight
# failure, not a module-import crash.
_TASKMANAGER_SO_RELPATH = "plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so"
_TASKMANAGER_QML_RELPATH = "plasma/applet/org/kde/mac/tahoe/liquid/taskmanager"
_LAUNCHER_QML_RELPATH = "org/kde/mac/tahoe/launcher"


def __getattr__(name: str):
    if name == "TASKMANAGER_DEST_SO":
        return qt6_plugins_dir() / _TASKMANAGER_SO_RELPATH
    if name == "TASKMANAGER_DEST_QML":
        return qt6_qml_dir() / _TASKMANAGER_QML_RELPATH
    if name == "LAUNCHER_DEST_QML":
        return qt6_qml_dir() / _LAUNCHER_QML_RELPATH
    raise AttributeError(name)
# Leftover from old sudoless installs under the user path.
LEGACY_TASKMANAGER_USER_SO = HOME / (
    ".local/lib/qt6/plugins/plasma/applets/"
    "org.kde.mac.tahoe.liquid.taskmanager.so"
)

LEGACY_DIRS = (
    "org.kde.mac.tahoe.liquid.taskmanager",
    "org.kde.mac-tahoe-liquid-kde.taskmanager",
    "org.kde.mac-tahoe-liquid-kde.icontasks",
)
# org.kde.plasma.taskmanager / org.kde.plasma.icontasks used to be in this
# tuple (this project briefly overlaid the stock IDs before it had its own
# namespace) — dropped because those IDs aren't ours: they're the real
# upstream Plasma applet IDs, and "install a local QML override at
# ~/.local/share/plasma/plasmoids/<id>" is a documented, common KDE
# customisation. Cleanup here can't tell "our old leftover" apart from a
# user's own override of the same stock plasmoid, so it must not touch
# them at all rather than risk deleting someone else's customization.
LEGACY_TASKMANAGER_QML_DIRS = (
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/taskmanager",
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac/tahoe/liquid/icontasks",
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac-tahoe-liquid-kde/taskmanager",
    HOME / ".local/lib/qt6/qml/plasma/applet/org/kde/mac-tahoe-liquid-kde/icontasks",
)

def deps():
    dependencies = [
        "qmake6:qt6-base",
        "qt6-svg-icons",
        "qt6-gui-cmake:qt6-base",
        "qt6-widgets-cmake:qt6-base",
        "qt6-dbus-cmake:qt6-base",
        "qt6-qml-cmake:qt6-declarative",
        "qt6-folderlistmodel-qml:qt6-declarative",
        "qt6-core-qml:qt6-declarative",
        "plasma5support-qml:plasma5support",
        "plasma-network-qml:plasma-nm",
        "plasma-audio-qml:plasma-pa",
        "plasma-power-qml:powerdevil",
        "bluez-qml:bluez-qt",
        "kf6-itemmodels-qml:kitemmodels",
        "qt6-wayland-cmake:qt6-wayland",
        "wayland-cmake:wayland",
        "cmake",
        "ecm:extra-cmake-modules",
        "make",
        "g++:gcc",
        "pkg-config:pkgconf",
        # KF6 components required by the taskmanager CMakeLists.
        "kf6-config-cmake:kconfig",
        "kf6-coreaddons-cmake:kcoreaddons",
        "kf6-i18n-cmake:ki18n",
        "kf6-kio-cmake:kio",
        "kf6-notifications-cmake:knotifications",
        "kf6-service-cmake:kservice",
        "kf6-windowsystem-cmake:kwindowsystem",
        "kf6-itemmodels-cmake:kitemmodels",
        # Plasma / KSysGuard / plasma-workspace (provides
        # LibNotificationManager + LibTaskManager cmake config).
        "plasma-cmake:libplasma",
        "plasma-activities-cmake:plasma-activities",
        "plasma-activities-stats-cmake:plasma-activities-stats",
        "ksysguard-cmake:libksysguard",
        "libnotificationmanager-cmake:plasma-workspace",
    ]
    if selected().get("desktop_widgets"):
        dependencies.append("zstd")
    return dependencies


def build_artifacts() -> list[Path]:
    return [
        TASKMANAGER_BUILD / "bin/plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so",
        TASKMANAGER_BUILD / "bin/plasma/applet/org/kde/mac/tahoe/liquid/taskmanager",
        TASKMANAGER_BUILD / "bin" / _LAUNCHER_QML_RELPATH / "libmactahoelauncher.so",
    ]


def build() -> None:
    if (TASKMANAGER_SRC / "CMakeLists.txt").is_file():
        cmake_build(TASKMANAGER_SRC, TASKMANAGER_BUILD, "Dock Task Manager")


def _migrate_appletsrc() -> None:
    # The rename lives in a bundled kconf_update helper; run just
    # that one so the upgrade keeps the dock and the user's pinned launchers.
    from steps.kconf_update import run_migration
    run_migration("mac-tahoe-migrate-appletsrc.sh")
    ok(tr('dock config migrated to MacTahoe dock fork'))


def _install_taskmanager_package() -> bool:
    """Install the dock applet's QML/runtime package. The .so alone is not
    enough: the icons-only wrapper resolves via X-Plasma-RootPath and needs
    the package metadata + contents/ in the local plasmoid dir too."""
    metadata = TASKMANAGER_SRC / "metadata.json"
    contents = TASKMANAGER_SRC / "contents"
    if not metadata.is_file():
        fail(tr('org.kde.mac.tahoe.liquid.taskmanager (missing metadata.json)'))
        return False
    if not contents.is_dir():
        fail(tr('org.kde.mac.tahoe.liquid.taskmanager (missing contents/)'))
        return False

    with temp_dir("mttkde-taskmanager-package") as tmp:
        runtime = tmp / TASKMANAGER_SRC.name
        runtime.mkdir(parents=True, exist_ok=True)
        shutil.copy2(metadata, runtime / "metadata.json")
        shutil.copytree(contents, runtime / "contents", symlinks=True)
        return install_tree(runtime, DEST_DIR / TASKMANAGER_SRC.name,
                            TASKMANAGER_SRC.name)


def _install_taskmanager_qml() -> bool:
    module_src = TASKMANAGER_BUILD / "bin/plasma/applet/org/kde/mac/tahoe/liquid/taskmanager"
    if not module_src.is_dir():
        fail(tr('org.kde.mac.tahoe.liquid.taskmanager (missing runtime QML)'))
        return False
    return sudo_install_tree(
        module_src, qt6_qml_dir() / _TASKMANAGER_QML_RELPATH,
        tr('org.kde.mac.tahoe.liquid.taskmanager (installed runtime QML)'),
        directory_root=qt6_qml_dir(),
    )


APPS_ENTRY = "org.kde.mac-tahoe-liquid-kde.apps.desktop"


def _install_launcher_package(widget: Path) -> bool:
    remember_installed_edition(HOME, DEST_DIR / widget.name)
    with temp_dir("mttkde-launcher-package") as tmp:
        staged = tmp / widget.name
        shutil.copytree(widget, staged, symlinks=True)
        apply_launcher_default(staged)
        if not install_tree(staged, DEST_DIR / widget.name, widget.name):
            return False
        applications = DATA_HOME / "applications"
        applications.mkdir(parents=True, exist_ok=True)
        shutil.copy2(widget / APPS_ENTRY, applications / APPS_ENTRY)
        return True


def install() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    choices = selected()
    if choices:
        install_desktop_widgets(choices["desktop_widgets"])

    dest_qml = qt6_qml_dir() / _TASKMANAGER_QML_RELPATH
    for name in LEGACY_DIRS:
        d = DEST_DIR / name
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
            ok(tr('{name} (removed local override)', name=name))
    for qml_dir in LEGACY_TASKMANAGER_QML_DIRS:
        if qml_dir != dest_qml:
            remove_tree(qml_dir, qml_dir.name)
    if LEGACY_TASKMANAGER_USER_SO.is_file():
        try:
            LEGACY_TASKMANAGER_USER_SO.unlink()
            ok(tr('{value1} (user-path leftover)', value1=LEGACY_TASKMANAGER_USER_SO.name))
        except OSError:
            pass

    from installer_choices import keep_panel_layout
    preserve_layout = keep_panel_layout()
    if not preserve_layout:
        _migrate_appletsrc()

    artifact = TASKMANAGER_BUILD / "bin/plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so"
    if artifact.is_file():
        if sudo_install_file(
            artifact, qt6_plugins_dir() / _TASKMANAGER_SO_RELPATH,
            tr('org.kde.mac.tahoe.liquid.taskmanager (installed compiled dock base)'),
            directory_root=qt6_plugins_dir(),
        ):
            _install_taskmanager_package()
            _install_taskmanager_qml()
    else:
        fail(tr('org.kde.mac.tahoe.liquid.taskmanager (missing build artifact)'))

    launcher_module = TASKMANAGER_BUILD / "bin" / _LAUNCHER_QML_RELPATH
    if (launcher_module / "libmactahoelauncher.so").is_file():
        sudo_install_tree(launcher_module, qt6_qml_dir() / _LAUNCHER_QML_RELPATH,
                          tr('Launcher (installed native search popup)'), directory_root=qt6_qml_dir())
    else:
        fail(tr('Launcher (missing native search popup build artifact)'))

    n = 0
    for widget in sorted(SRC_DIR.glob("*/")):
        if not widget.is_dir():
            continue
        # C++ applets are installed via their own build steps.
        if (widget / "CMakeLists.txt").is_file():
            continue
        # Panel Colorizer is installed by the layout step behind a
        # presence check so an existing copy isn't clobbered.
        if widget.name == "luisbocanegra.panel.colorizer":
            continue
        if not (widget / "metadata.json").is_file():
            fail(tr('{value1} (no metadata.json — skipping)', value1=widget.name))
            continue
        if widget.name == LAUNCHER_ID:
            from installer_choices import launcher_preference, use_user_launcher
            if use_user_launcher():
                if (DEST_DIR / LAUNCHER_ID).is_dir():
                    if preserve_layout:
                        continue
                    (DATA_HOME / "applications" / APPS_ENTRY).unlink(missing_ok=True)
                    from steps.layout import replace_project_launcher
                    replace_project_launcher()
                    if not remove_tree(DEST_DIR / LAUNCHER_ID, LAUNCHER_ID):
                        raise RuntimeError("Could not remove the project launcher")
                marker = launcher_preference()
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.touch()
                continue
        installed = (_install_launcher_package(widget) if widget.name == LAUNCHER_ID
                     else install_tree(widget, DEST_DIR / widget.name))
        if installed:
            if widget.name == LAUNCHER_ID:
                launcher_preference().unlink(missing_ok=True)
            n += 1
    spacing_script = offline("layouts/dock-spacing.js")
    if not preserve_layout and spacing_script.is_file():
        qdbus_call("org.kde.plasmashell", "/PlasmaShell",
                   "org.kde.PlasmaShell.evaluateScript", spacing_script.read_text())
    label = "plasmoid" if n == 1 else "plasmoids"
    info(tr('{n} {label} installed/reinstalled', n=n, label=tr(label)))


def uninstall() -> None:
    _remove_desktop_widgets()
    from installer_choices import launcher_preference
    launcher_preference().unlink(missing_ok=True)
    (DATA_HOME / "applications" / APPS_ENTRY).unlink(missing_ok=True)
    n = 0
    dest_so = qt6_plugins_dir() / _TASKMANAGER_SO_RELPATH
    dest_qml = qt6_qml_dir() / _TASKMANAGER_QML_RELPATH
    if sudo_remove(dest_so, dest_so.name):
        n += 1
    if sudo_remove(dest_qml, dest_qml.name):
        n += 1
    if not (qt6_plugins_dir() / "plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so").is_file():
        if sudo_remove(qt6_qml_dir() / _LAUNCHER_QML_RELPATH, tr('Launcher native search popup')):
            n += 1
    if LEGACY_TASKMANAGER_USER_SO.is_file():
        try:
            LEGACY_TASKMANAGER_USER_SO.unlink()
            ok(tr('{value1} (user-path leftover)', value1=LEGACY_TASKMANAGER_USER_SO.name)); n += 1
        except OSError:
            pass
    targets = [
        DEST_DIR / "org.kde.mac.tahoe.liquid.taskmanager",
        DEST_DIR / "org.kde.mac.tahoe.liquid.icontasks",
        *DEST_DIR.glob("org.kde.mac-tahoe-liquid-kde.*"),
        *DEST_DIR.glob("org.kde.mactahoe-liquid-kde.*"),
    ]
    for d in targets:
        if d.is_dir():
            try:
                shutil.rmtree(d)
                ok(d.name); n += 1
            except OSError:
                fail(d.name)
    info(tr('{n} plasmoids removed', n=n))

def _installed_widgets() -> set[str]:
    try:
        entries = WIDGETS_STATE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return set()
    return {name for name in entries if WIDGET_ID.fullmatch(name)}


def _save_installed_widgets(names: set[str]) -> None:
    if not names:
        WIDGETS_STATE.unlink(missing_ok=True)
        return
    WIDGETS_STATE.parent.mkdir(parents=True, exist_ok=True)
    stream = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=WIDGETS_STATE.parent, delete=False)
    pending = Path(stream.name)
    try:
        with stream:
            stream.writelines(name + "\n" for name in sorted(names))
        pending.replace(WIDGETS_STATE)
    finally:
        pending.unlink(missing_ok=True)


def _remove_desktop_widgets() -> None:
    _remove_placed_desktop_widgets()
    remaining = set()
    for name in sorted(_installed_widgets()):
        target = DEST_DIR / name
        if target.is_dir() and not target.is_symlink() and not remove_tree(target, name):
            remaining.add(name)
    _save_installed_widgets(remaining)


def install_desktop_widgets(enabled: bool) -> None:
    """Manage the optional widget pack without taking over user installations."""
    if not enabled:
        _remove_desktop_widgets()
        return
    if not WIDGETS_ARCHIVE.is_file():
        warn(tr('Liquid Glass desktop widgets not found — skipping'))
        return
    with temp_dir("mttkde-desktop-widgets-") as staging:
        result = subprocess.run(["tar", "--zstd", "-xf", str(WIDGETS_ARCHIVE), "-C", str(staging)],
                                check=False, capture_output=True, text=True)
        if result.returncode != 0:
            warn(tr('Liquid Glass desktop widgets could not be unpacked: {error}', error=result.stderr.strip()))
            return
        installed = _installed_widgets()
        for entry in sorted(staging.iterdir()):
            name = entry.name
            if not WIDGET_ID.fullmatch(name) or not (entry / "metadata.json").is_file():
                continue
            target = DEST_DIR / name
            if target.is_symlink() or (target.exists() and name not in installed):
                continue
            if install_tree(entry, target, name):
                installed.add(name)
                _save_installed_widgets(installed)


def _run_widget_script(script: str) -> dict:
    command = qdbus_cmd()
    if not command:
        raise RuntimeError("Plasma scripting is unavailable")
    result = run_user([command, "org.kde.plasmashell", "/PlasmaShell",
                       "org.kde.PlasmaShell.evaluateScript", script],
                      check=True, capture_output=True, text=True, timeout=15)
    return json.loads(result.stdout)


def place_desktop_widgets() -> None:
    """Place the illustrated starter set once, after Plasma loads the packages."""
    if not selected().get("desktop_widgets"):
        return
    placement = WIDGETS_STATE.with_suffix(".placed.json")
    if placement.exists():
        return
    script = """
    (function () {
        const names = NAMES;
        const desk = Array.from(desktopsForActivity(currentActivity())).find(d => d.screen === 0);
        if (!desk || !names.every(name => knownWidgetTypes.includes(name))) {
            throw new Error("Desktop widgets are unavailable");
        }
        const area = screenGeometry(0);
        const size = Math.min(208, Math.max(160, Math.floor((area.height - 188) / 3)));
        const step = size + 20;
        let x = 48;
        let y = 76;
        const placed = {};
        const widgets = desk.widgets();
        for (const name of names) {
            if (widgets.some(w => w.type === name)) continue;
            while (x + size <= area.width - 48) {
                if (y + size > area.height - 72) {
                    x += step;
                    y = 76;
                    continue;
                }
                const occupied = widgets.some(w => {
                    const r = w.geometry;
                    return r.x < x + size && x < r.x + r.width &&
                           r.y < y + size && y < r.y + r.height;
                });
                if (!occupied) break;
                y += step;
            }
            if (x + size > area.width - 48) break;
            const widget = desk.addWidget(name, x, y, size, size);
            if (widget) placed[widget.id] = name;
            y += step;
        }
        print(JSON.stringify(placed));
    })();
    """.replace("NAMES", json.dumps(DESKTOP_STARTERS))
    placed = _run_widget_script(script)
    placement.parent.mkdir(parents=True, exist_ok=True)
    placement.write_text(json.dumps(placed), encoding="utf-8")


def _remove_placed_desktop_widgets() -> None:
    placement = WIDGETS_STATE.with_suffix(".placed.json")
    try:
        placed = json.loads(placement.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    if placed:
        _run_widget_script("""
        (function () {
            const placed = PLACED;
            for (const desk of desktops()) {
                for (const widget of desk.widgets()) {
                    if (placed[widget.id] === widget.type) widget.remove();
                }
            }
            print("{}");
        })();
        """.replace("PLACED", json.dumps(placed)))
    placement.unlink()
