#!/usr/bin/env python3
"""Capture real themed popup families in a private KWin session.

Requires PyQt6, GTK 3/4 introspection, KWin, Spectacle and qdbus6.
Never installs assets or changes the running desktop. Output must be new.
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import resource
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/scripts"))
from acrylic_glass_capture import wait_for, stop, assert_compositor_owner

CASES = (
    "menu",
    "context",
    "submenu",
    "combo",
    "tooltip",
    "dialog",
    "plasma",
    "dock",
    "gtk3-menu",
    "gtk3-popover",
    "gtk4-popover",
)


def qt_client(case, output):
    from PyQt6.QtCore import QPoint, QTimer, Qt
    from PyQt6.QtGui import QAction, QColor, QPainter, QPalette, QCursor
    from PyQt6.QtWidgets import (
        QApplication,
        QMainWindow,
        QWidget,
        QVBoxLayout,
        QLabel,
        QPushButton,
        QMenu,
        QComboBox,
        QToolTip,
        QDialog,
    )

    def report_error(exc_type, exc, tb):
        import traceback

        (output / "client-error.txt").write_text(
            "".join(traceback.format_exception(exc_type, exc, tb))
        )
        sys.__excepthook__(exc_type, exc, tb)
        os._exit(1)

    sys.excepthook = report_error
    app = QApplication(sys.argv)
    app.setDesktopFileName("mttkde-popup-probe")
    if case == "background":

        class Background(QWidget):
            def paintEvent(self, event):
                p = QPainter(self)
                for y in range(0, self.height(), 24):
                    for x in range(0, self.width(), 24):
                        p.fillRect(
                            x,
                            y,
                            24,
                            24,
                            QColor("#49687b" if (x // 24 + y // 24) % 2 else "#ceb886"),
                        )

        window = Background(None, Qt.WindowType.FramelessWindowHint)
        if "dock" in os.environ.get("PROBE_CASES", "").split(","):
            # A fullscreen client can cover X11 Dock windows in KWin's stack.
            window.showMaximized()
        else:
            window.showFullScreen()
        app.exec()
        return
    if case in ("plasma", "dock"):
        from PyQt6.QtQml import QQmlApplicationEngine

        engine = QQmlApplicationEngine()
        if case == "dock":
            engine.loadData(b"""
import QtQuick
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
PlasmaCore.Dialog {
    visible: true
    x: 180; y: 520
    type: PlasmaCore.Dialog.Dock
    location: PlasmaCore.Types.Floating
    mainItem: Item {
        width: 560; height: 64
        Row {
            anchors.centerIn: parent
            spacing: 24
            Repeater {
                model: ["system-file-manager", "applications-internet", "utilities-terminal",
                        "systemsettings", "user-trash"]
                Kirigami.Icon { required property string modelData; source: modelData; width: 40; height: 40 }
            }
        }
    }
}
""")
        else:
            engine.loadData(b"""
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PC
PlasmaCore.Dialog {
    visible: true
    x: 380; y: 240
    type: PlasmaCore.Dialog.PopupMenu
    location: PlasmaCore.Types.Floating
    mainItem: ColumnLayout {
        width: 320; height: 260
        PC.Label { text: "Plasma popup"; Layout.alignment: Qt.AlignHCenter }
        PC.Button { text: "About This Computer"; Layout.fillWidth: true }
        PC.Button { text: "System Settings"; Layout.fillWidth: true }
        PC.CheckBox { text: "Show hidden files"; checked: true }
        PC.TextField { placeholderText: "Search"; Layout.fillWidth: true }
        PC.Label { text: "Disabled action"; enabled: false }
    }
}
""")
        assert engine.rootObjects(), "Plasma QML did not load"
        QTimer.singleShot(1500, lambda: (output / "ready").write_text(case))
        app.exec()
        return
    app.setStyle("MacTahoe" if os.environ.get("PROBE_MENU_STYLE") else "kvantum")
    dark = os.environ["PROBE_MODE"] == "Dark"
    palette = app.palette()
    for role, color in (
        (QPalette.ColorRole.Window, "#202020" if dark else "#f6f6f6"),
        (QPalette.ColorRole.WindowText, "#eeeeee" if dark else "#222222"),
        (QPalette.ColorRole.Text, "#eeeeee" if dark else "#222222"),
        (QPalette.ColorRole.Base, "#292929" if dark else "#ffffff"),
    ):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    window = QMainWindow()
    window.setWindowTitle("Popup visual probe")
    body = QWidget()
    layout = QVBoxLayout(body)
    layout.addWidget(QLabel("Menus, controls and popup geometry"))
    button = QPushButton("Open menu")
    layout.addWidget(button)
    combo = QComboBox()
    combo.addItems(["Light", "Dark", "Automatic"])
    layout.addWidget(combo)
    layout.addWidget(QLabel("Normal text • Disabled text • Selected text"))
    window.setCentralWidget(body)
    window.resize(480, 320)
    window.show()
    menu = QMenu(window)
    menu.addAction("Open", lambda: None).setShortcut("Ctrl+O")
    menu.addAction("Open Recent")
    sub = menu.addMenu("More Actions")
    sub.addActions(
        [QAction(t, sub) for t in ("Duplicate", "Move to Trash", "Properties")]
    )
    menu.addSeparator()
    checked = menu.addAction("Show hidden files")
    checked.setCheckable(True)
    checked.setChecked(True)
    menu.addAction("Unavailable action").setEnabled(False)
    menu.addAction("Properties").setShortcut("Alt+Return")
    window.menuBar().addMenu(menu).setText("File")
    dialog = QDialog(window)
    dl = QVBoxLayout(dialog)
    dl.addWidget(QLabel("Dialog surface and rounded corners"))
    dl.addWidget(QPushButton("Continue"))
    dialog.resize(360, 180)

    def show():
        # KWindowSystem discovers blur capability asynchronously. Commit a
        # second frame so the probe measures the settled protocol state.
        QTimer.singleShot(
            400, lambda: [w.update() for w in app.topLevelWidgets() if w.isVisible()]
        )
        QTimer.singleShot(800, ready)
        point = window.mapToGlobal(QPoint(90, 90))
        if case in ("menu", "context", "submenu"):
            if case == "menu":
                point = window.menuBar().mapToGlobal(
                    QPoint(0, window.menuBar().height())
                )
            menu.popup(point)
            if case == "submenu":
                menu.setActiveAction(sub.menuAction())
                sub.popup(
                    menu.mapToGlobal(
                        QPoint(
                            menu.width() - 2,
                            menu.actionGeometry(sub.menuAction()).top(),
                        )
                    )
                )
        elif case == "combo":
            combo.showPopup()
        elif case == "tooltip":
            QToolTip.showText(
                QCursor.pos(),
                "Tooltip with two lines\nKeyboard shortcut: Ctrl+O",
            )
        elif case == "dialog":
            dialog.show()

    def ready():
        entries = []
        for widget in app.topLevelWidgets():
            if widget.isVisible():
                rect = widget.frameGeometry()
                entries.append(
                    {
                        "type": widget.metaObject().className(),
                        "rect": [rect.x(), rect.y(), rect.width(), rect.height()],
                    }
                )
        if case in ("menu", "context", "submenu"):
            assert menu.isVisible(), "Popup did not open"
        if case == "submenu":
            assert sub.isVisible(), "Submenu did not open"
        if case == "combo":
            assert combo.view().isVisible(), "Combo did not open"
        if case == "tooltip":
            assert any(
                e["type"] == "QTipLabel" for e in entries
            ), f"Tooltip did not open: {entries}"
        (output / "geometry.json").write_text(json.dumps(entries, indent=2))
        (output / "ready").write_text(case)

    button.clicked.connect(lambda: QTimer.singleShot(250, show))
    if case in ("menu", "context", "submenu", "combo", "tooltip"):

        def request_input():
            center = app.primaryScreen().geometry().center()
            local = (
                button.mapTo(window, button.rect().center()) - window.rect().center()
            )
            (output / "input-ready").write_text(
                json.dumps([center.x() + local.x(), center.y() + local.y() + 18])
            )

        QTimer.singleShot(600, request_input)
    else:
        QTimer.singleShot(600, show)
    app.exec()


def gtk_client(case, output):
    import gi

    version = "4.0" if case.startswith("gtk4") else "3.0"
    gi.require_version("Gtk", version)
    from gi.repository import Gtk, GLib, Gio, Gdk

    app = Gtk.Application(application_id="org.example.PopupProbe")

    def activate(app):
        window = Gtk.ApplicationWindow(application=app, title="GTK popup visual probe")
        window.set_default_size(480, 320)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        label = Gtk.Label(label="GTK " + version + " menu and popover")
        button = (
            Gtk.MenuButton(label="Open menu") if version == "4.0" else Gtk.MenuButton()
        )
        if version == "3.0":
            button.set_label("Open menu")
            box.pack_start(label, False, False, 12)
            box.pack_start(button, True, True, 12)
            window.add(box)
        else:
            box.append(label)
            box.append(button)
            button.set_vexpand(True)
            window.set_child(box)
        model = Gio.Menu()
        for text in ("Open", "Copy", "Paste", "Show hidden files", "Properties"):
            model.append(text, "app.action")
        action = Gio.SimpleAction.new("action", None)
        app.add_action(action)
        if case == "gtk3-menu":
            menu = Gtk.Menu.new_from_model(model)
            button.set_popup(menu)
        else:
            menu = (
                Gtk.PopoverMenu.new_from_model(model)
                if version == "4.0"
                else Gtk.Popover.new_from_model(button, model)
            )
            button.set_popover(menu)
        window.present() if version == "4.0" else window.show_all()

        def mapped(widget):
            GLib.timeout_add(
                800, lambda: ((output / "ready").write_text(case), False)[1]
            )

        menu.connect("map", mapped)

        def request_input():
            (output / "input-ready").write_text(json.dumps([550, 410]))
            return False

        GLib.timeout_add(800, request_input)

    app.connect("activate", activate)
    app.run([])


def session(output):
    (output / "session.json").write_text(json.dumps(dict(os.environ)))
    while True:
        time.sleep(1)


def inside(output):
    for key, expected in (
        ("HOME", output / "home"),
        ("XDG_CONFIG_HOME", output / "config"),
        ("PROBE_OUTPUT", output),
    ):
        if os.environ.get(key) != str(expected):
            raise RuntimeError("Private environment required")
    processes = []
    script = str(Path(__file__).resolve())

    def dbus(*args):
        return subprocess.check_output(
            ["qdbus6", "org.kde.KWin", *args], text=True, timeout=10
        ).strip()

    def capture(path, env):
        with (output / "spectacle.log").open("a") as log:
            subprocess.run(
                [
                    "spectacle",
                    "--background",
                    "--nonotify",
                    "--fullscreen",
                    "--output",
                    str(path),
                ],
                env=env,
                stdout=log,
                stderr=log,
                check=True,
                timeout=20,
            )
        assert path.is_file(), "Missing screenshot"

    try:
        with (output / "kwin.log").open("w") as log:
            kwin = subprocess.Popen(
                [
                    str(output / "bin/kwin_wayland"),
                    "--virtual",
                    "--xwayland",
                    "--scale",
                    os.environ["PROBE_SCALE"],
                    "--width",
                    "1100",
                    "--height",
                    "780",
                    "--no-lockscreen",
                    "--no-global-shortcuts",
                    "--no-kactivities",
                    "--exit-with-session",
                    shlex.join([sys.executable, script, "--session", str(output)]),
                ],
                stdout=log,
                stderr=log,
            )
        processes.append(kwin)
        wait_for(lambda: (output / "session.json").exists())
        assert_compositor_owner(kwin.pid)
        env = json.loads((output / "session.json").read_text())
        env["QT_QPA_PLATFORM"] = "wayland"
        with (output / "background.log").open("w") as log:
            background = subprocess.Popen(
                [
                    sys.executable,
                    script,
                    "--client",
                    "background",
                    "--output",
                    str(output),
                ],
                env=env,
                stdout=log,
                stderr=log,
            )
        processes.append(background)
        time.sleep(1)
        manifest = []
        for case in os.environ["PROBE_CASES"].split(","):
            for effect in ("liquidglass", "kwin4_effect_shapecorners"):
                assert (
                    dbus("/Effects", "org.kde.kwin.Effects.loadEffect", effect)
                    == "true"
                )
            time.sleep(0.4)
            case_output = output / case
            case_output.mkdir()
            client_env = env | {
                "QT_QPA_PLATFORM": os.environ["PROBE_BACKEND"],
                "GDK_BACKEND": (
                    "x11" if os.environ["PROBE_BACKEND"] == "xcb" else "wayland"
                ),
            }
            if case == "dock":
                # Dialog supplies the native Dock role and blur mask. Use the
                # real panel surface instead of its light/dark popup fill.
                theme = "MacTahoeLiquidKde-" + os.environ["PROBE_MODE"]
                theme_root = output / "data/plasma/desktoptheme"
                dock_theme = theme_root / "DockProbe"
                shutil.copytree(theme_root / theme, dock_theme)
                shutil.copyfile(dock_theme / "widgets/panel-background.svgz",
                                dock_theme / "dialogs/background.svgz")
                dock_config = case_output / "config"
                shutil.copytree(output / "config", dock_config)
                (dock_config / "plasmarc").write_text("[Theme]\nname=DockProbe\n")
                client_env["XDG_CONFIG_HOME"] = str(dock_config)
            with (case_output / "client.log").open("w") as log:
                client = subprocess.Popen(
                    [
                        sys.executable,
                        script,
                        "--client",
                        case,
                        "--output",
                        str(case_output),
                    ],
                    env=client_env,
                    stdout=log,
                    stderr=log,
                )
            processes.append(client)
            wait_for(
                lambda: (case_output / "ready").exists()
                or (case_output / "input-ready").exists()
                or client.poll() is not None
            )
            if (case_output / "input-ready").exists():
                x, y = json.loads((case_output / "input-ready").read_text())
                subprocess.run(
                    [str(output / "bin/menu-wayland-pointer"), str(x), str(y), "click"],
                    env=env | {"PROBE_COMPOSITOR_PID": str(kwin.pid)},
                    check=True,
                    timeout=5,
                )
                wait_for(
                    lambda: (case_output / "ready").exists()
                    or client.poll() is not None
                )
            assert (
                client.poll() is None
            ), f"{case} exited ({client.returncode}); inspect client.log"
            for state in ("on", "off"):
                for effect in ("liquidglass", "kwin4_effect_shapecorners"):
                    if state == "off":
                        dbus("/Effects", "org.kde.kwin.Effects.unloadEffect", effect)
                time.sleep(0.7)
                if state == "on":
                    active = dbus(
                        "/Effects", "org.kde.kwin.Effects.activeEffects"
                    ).splitlines()
                    assert all(
                        e in active
                        for e in ("liquidglass", "kwin4_effect_shapecorners")
                    ), active
                    for effect in ("liquidglass", "kwin4_effect_shapecorners"):
                        plugin = output / f"plugins/kwin/effects/plugins/{effect}.so"
                        mappings = [
                            line
                            for line in Path(f"/proc/{kwin.pid}/maps")
                            .read_text()
                            .splitlines()
                            if f"/{effect}.so" in line
                        ]
                        assert mappings and all(
                            line.split(maxsplit=5)[5] == str(plugin)
                            and int(line.split()[4]) == plugin.stat().st_ino
                            for line in mappings
                        )
                capture(case_output / f"{state}.png", env)
            if case == "dock":
                from PIL import Image, ImageChops

                with Image.open(case_output / "on.png") as enabled, Image.open(case_output / "off.png") as disabled:
                    assert ImageChops.difference(enabled.convert("RGB"), disabled.convert("RGB")).getbbox(), "Dock glass was not visible"
            manifest.append({"case": case, "captured": True})
            stop(client)
            processes.remove(client)
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    finally:
        for process in reversed(processes):
            stop(process)


def run(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for name in ("home", "config", "data", "cache", "bin"):
        (output / name).mkdir()
    shutil.copyfile(shutil.which("kwin_wayland"), output / "bin/kwin_wayland")
    (output / "bin/kwin_wayland").chmod(0o755)
    shutil.copyfile(args.pointer, output / "bin/menu-wayland-pointer")
    (output / "bin/menu-wayland-pointer").chmod(0o755)
    applications = output / "data/applications"
    applications.mkdir()
    (applications / "org.kde.mttkde.menu-probe.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Isolated menu probe\nExec="
        + str(output / "bin/menu-wayland-pointer")
        + "\nNoDisplay=true\nX-KDE-Wayland-Interfaces=org_kde_kwin_fake_input\n"
    )
    plugin_dir = output / "plugins/kwin/effects/plugins"
    plugin_dir.mkdir(parents=True)
    if args.menu_style:
        styles = output / "plugins/styles"
        styles.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.menu_style, styles / "libmactahoestyle.so")
    shutil.copyfile(args.glass, plugin_dir / "liquidglass.so")
    shutil.copyfile(args.rounded, plugin_dir / "kwin4_effect_shapecorners.so")
    shaders = output / "data/kwin/shaders"
    shaders.mkdir(parents=True)
    for name in ("shapecorners.frag", "shapecorners_core.frag"):
        shutil.copyfile(args.shaders / name, shaders / name)
    mode = args.mode
    theme = "MacTahoeLiquidKde-" + mode
    kv = "mac-tahoe-liquid-kde" + ("Dark" if mode == "Dark" else "")
    for kind, source, dest, name in (
        (
            "plasma",
            ROOT / "src/offline/plasma-theme" / theme,
            output / "data/plasma/desktoptheme" / (theme),
            theme,
        ),
        (
            "gtk",
            ROOT / "src/offline/gtk" / theme,
            output / "home/.themes" / (theme),
            theme,
        ),
        (
            "kvantum",
            ROOT / "src/offline/kvantum/mac-tahoe-liquid-kde",
            output / "config/Kvantum" / (kv),
            kv,
        ),
    ):
        shutil.copytree(source, dest)
    (output / "config/Kvantum/kvantum.kvconfig").write_text(
        "[General]\ntheme=" + kv + "\n"
    )
    (output / "config/plasmarc").write_text("[Theme]\nname=" + theme + "\n")
    colors = (
        ROOT / "src/offline/color-schemes" / ("MacTahoeLiquidKde" + mode + ".colors")
    )
    shutil.copyfile(colors, output / "config/kdeglobals")
    from steps.acrylic_glass import _CORNER_DEFAULTS

    profiles = json.loads((ROOT / "src/offline/kwin-effects/acrylic-glass/src/presets.json").read_text())
    profile = next(profile for profile in profiles if profile["id"] == args.material)
    preset = {key: str(value).lower() if isinstance(value, bool) else str(value)
              for key, value in profile["values"].items()}
    preset.update(_CORNER_DEFAULTS)
    preset["MaterialPreset"] = str(profile["value"])
    preset["WindowClasses"] = "capture-desktop"
    (output / "config/kwinrc").write_text(
        "[Plugins]\nblurEnabled=false\nliquidglassEnabled=false\nkwin4_effect_shapecornersEnabled=false\n"
        "[Windows]\nPlacement=Centered\n[Effect-liquidglass]\n"
        + "".join(f"{key}={value}\n" for key, value in preset.items())
        + "[Round-Corners]\nSize=28\nInactiveCornerRadius=28\nAnimationDuration=0\n"
    )
    with tempfile.TemporaryDirectory(prefix="menus-") as runtime:
        env = {
            k: v
            for k, v in os.environ.items()
            if k in ("PATH", "LANG", "USER", "LOGNAME")
        }
        env.update(
            HOME=str(output / "home"),
            XDG_CONFIG_HOME=str(output / "config"),
            XDG_DATA_HOME=str(output / "data"),
            XDG_CACHE_HOME=str(output / "cache"),
            XDG_RUNTIME_DIR=runtime,
            QT_PLUGIN_PATH=str(output / "plugins"),
            PROBE_MENU_STYLE="1" if args.menu_style else "",
            QT_QPA_PLATFORM="offscreen",
            QT_QUICK_CONTROLS_STYLE="org.kde.desktop",
            QT_QPA_PLATFORMTHEME="kde",
            NO_AT_BRIDGE="1",
            GTK_A11Y="none",
            GTK_THEME=theme,
            GTK_USE_PORTAL="0",
            GIO_USE_VFS="local",
            QT_IM_MODULE="compose",
            GTK_IM_MODULE="gtk-im-context-simple",
            LIBGL_ALWAYS_SOFTWARE="1",
            KWIN_COMPOSE="O2",
            PROBE_OUTPUT=str(output),
            PROBE_MODE=mode,
            PROBE_BACKEND=args.backend,
            PROBE_SCALE=str(args.scale),
            PROBE_CASES=",".join(args.cases),
        )
        with (output / "sycoca.log").open("w") as log:
            subprocess.run(
                ["kbuildsycoca6", "--noincremental"],
                env=env,
                stdout=log,
                stderr=log,
                check=True,
                timeout=30,
            )
        proc = subprocess.Popen(
            [
                "dbus-run-session",
                "--",
                sys.executable,
                str(Path(__file__).resolve()),
                "--inside",
                str(output),
            ],
            env=env,
            start_new_session=True,
        )
        try:
            if proc.wait(timeout=240):
                raise RuntimeError("Visual probe failed")
        finally:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            stop(proc)
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


if __name__ == "__main__":
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--pointer", type=Path, default=ROOT / "build/menu-probe/menu-wayland-pointer"
    )
    parser.add_argument("--menu-style", type=Path)
    parser.add_argument("--glass", type=Path)
    parser.add_argument("--rounded", type=Path)
    parser.add_argument("--shaders", type=Path)
    parser.add_argument("--mode", choices=("Light", "Dark"), default="Light")
    parser.add_argument("--material", choices=("tahoe", "golden-gate"), default="tahoe")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--backend", choices=("wayland", "xcb"), default="wayland")
    parser.add_argument("--cases", nargs="+", choices=CASES, default=CASES)
    parser.add_argument("--client")
    parser.add_argument("--session", type=Path)
    parser.add_argument("--inside", type=Path)
    args = parser.parse_args()
    if args.client:
        (gtk_client if args.client.startswith("gtk") else qt_client)(
            args.client, args.output
        )
    elif args.session:
        session(args.session)
    elif args.inside:
        inside(args.inside)
    else:
        for name in ("output", "glass", "rounded", "shaders"):
            if getattr(args, name) is None:
                parser.error("--" + name + " is required")
        if not 0.5 <= args.scale <= 3:
            parser.error("--scale must be between 0.5 and 3")
        run(args)
