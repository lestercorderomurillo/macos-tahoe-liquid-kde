#!/usr/bin/env python3
"""Opt-in, isolated KWin pixel probe. Never installs on the desktop.

Uses a synthetic transparent VM surface; this is not a VirtualBox guest test.
Requires KWin, Spectacle, kscreen-doctor, qdbus6, PyQt6, Pillow and a compiled effect.
Use --backend xcb for Xwayland (also requires Xwayland).
Use --compositor x11 with the X11 plugin for native KWin X11 in Xvfb.
Add --wobbly --identity WobblyProbe --expect changed for drag coverage
(requires xdotool and xprop); compare glass at rest, during motion and afterward.
Use --identity VirtualBox --expect changed to check the manager is not excluded.
Use --expect changed for an unpatched control; unchanged is the default.
The output directory must be new. No host config or plugins are modified.
"""
from __future__ import annotations

import argparse
import hashlib
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


def wait_for(check, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.1)
    raise RuntimeError("Timed out waiting for isolated session")


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def client(role):
    from PyQt6.QtCore import Qt, QTimer, QRect
    from PyQt6.QtGui import QColor, QPainter
    from PyQt6.QtWidgets import QApplication, QWidget

    app = QApplication(sys.argv)
    app.setDesktopFileName(os.environ["MTTKDE_CAPTURE_IDENTITY"] if role == "vm" else "capture-desktop")

    rounded = os.environ.get("MTTKDE_CAPTURE_EFFECT") == "kwin4_effect_shapecorners"

    class Surface(QWidget):
        def paintEvent(self, event):
            painter = QPainter(self)
            if role == "desktop":
                for y in range(0, self.height(), 16):
                    for x in range(0, self.width(), 16):
                        painter.fillRect(x, y, 16, 16,
                                         QColor("#214263" if (x // 16 + y // 16) % 2 else "#e1c787"))
                if getattr(self, "patch_visible", False):
                    painter.fillRect(80, 80, 32, 32, QColor("#ed2244"))
            elif rounded:
                painter.fillRect(self.rect(), QColor("#3778aa"))
                if os.environ.get("MTTKDE_CAPTURE_COMPANION"):
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                    painter.fillRect(self.width() // 4, self.height() // 4,
                                     self.width() // 2, self.height() // 2, QColor(55, 120, 170, 100))
            else:
                painter.fillRect(self.width() // 3, self.height() // 3,
                                 self.width() // 3, self.height() // 3, QColor("#3778aa"))

    # Qt 6.10 does not map QWidget desktop windows on every Wayland backend.
    # The first fullscreen client supplies the background beneath the probe.
    flags = Qt.WindowType.Window if role == "vm" and rounded else Qt.WindowType.FramelessWindowHint
    window = Surface(None, flags)
    if role != "desktop":
        window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    window.setWindowTitle("Synthetic VM surface" if role == "vm" else "Capture background")
    if role == "desktop" and os.environ.get("MTTKDE_CAPTURE_DAMAGE"):
        marker = Path(os.environ["MTTKDE_CAPTURE_DIR"]) / "damage-trigger"
        timer = QTimer(window)
        def update_patch():
            if marker.exists() and not getattr(window, "patch_visible", False):
                window.patch_visible = True
                window.update(QRect(80, 80, 32, 32))
        timer.timeout.connect(update_patch)
        timer.start(50)
    if role == "vm" and os.environ.get("MTTKDE_CAPTURE_DESKTOP"):
        # Set the actual X11 desktop type before mapping on this private Xwayland.
        subprocess.run(["xprop", "-id", str(int(window.winId())), "-f", "_NET_WM_WINDOW_TYPE", "32a",
                        "-set", "_NET_WM_WINDOW_TYPE", "_NET_WM_WINDOW_TYPE_DESKTOP"], check=True, timeout=5)
    window.resize(960, 640)
    if role != "desktop" and (rounded or os.environ.get("MTTKDE_CAPTURE_WOBBLY")):
        window.resize(480, 320)
        window.show()
        if os.environ.get("MTTKDE_CAPTURE_WOBBLY"):
            subprocess.run(["xprop", "-id", str(int(window.winId())), "-f",
                            "_KDE_NET_WM_BLUR_BEHIND_REGION", "32c", "-set",
                            "_KDE_NET_WM_BLUR_BEHIND_REGION", "0,0,480,320"], check=True)
    else:
        window.showFullScreen()
    app.exec()


def session():
    output = Path(os.environ["MTTKDE_CAPTURE_DIR"])
    temporary = output / "session-env.tmp"
    temporary.write_text(json.dumps(dict(os.environ)))
    temporary.replace(output / "session-env.json")
    while True:
        time.sleep(1)


def assert_compositor_owner(pid):
    owner = subprocess.run([
        "qdbus6", "org.freedesktop.DBus", "/org/freedesktop/DBus",
        "org.freedesktop.DBus.GetConnectionUnixProcessID", "org.kde.KWin",
    ], capture_output=True, text=True, check=True, timeout=5)
    if int(owner.stdout.strip()) != pid:
        raise RuntimeError("D-Bus belongs to a different compositor; refusing mutations")


def inside(output):
    # Internal entry points must never accidentally operate on the real
    # desktop if invoked directly instead of through run().
    for key, expected in (("MTTKDE_CAPTURE_DIR", output),
                          ("HOME", output / "home"),
                          ("XDG_CONFIG_HOME", output / "config")):
        if os.environ.get(key) != str(expected):
            raise RuntimeError("Capture requires its private session environment")
    kwin = background = vm = xserver = None
    x11 = os.environ.get("MTTKDE_CAPTURE_COMPOSITOR") == "x11"
    plugin_family = "kwin-x11" if x11 else "kwin"
    effect = os.environ.get("MTTKDE_CAPTURE_EFFECT", "liquidglass")
    script = str(Path(__file__).resolve())

    def dbus(*args):
        return subprocess.run(["qdbus6", "org.kde.KWin", *args],
                              capture_output=True, text=True, check=True, timeout=10).stdout.strip()

    def capture(name, delay=1):
        time.sleep(delay)
        if os.environ.get("MTTKDE_CAPTURE_SCREENSHOT_API") == "dbus":
            import dbus as python_dbus
            from PyQt6.QtGui import QImage
            assert_compositor_owner(kwin.pid)
            bus = python_dbus.SessionBus()
            interface = python_dbus.Interface(bus.get_object("org.kde.KWin.ScreenShot2", "/org/kde/KWin/ScreenShot2"), "org.kde.KWin.ScreenShot2")
            with tempfile.TemporaryFile() as raw:
                metadata = interface.CaptureScreen("Virtual-0", python_dbus.Dictionary({}, signature="sv"), python_dbus.types.UnixFd(raw.fileno()), timeout=15)
                width, height, stride = (int(metadata[key]) for key in ("width", "height", "stride"))
                wait_for(lambda: os.fstat(raw.fileno()).st_size >= stride * height)
                raw.seek(0)
                pixels = raw.read()
                image = QImage(pixels, width, height, stride, QImage.Format(int(metadata["format"])))
                assert image.save(str(output / name)), "Raw compositor screenshot failed"
            return
        capture_env = env.copy()
        capture_env["QT_QPA_PLATFORM"] = "xcb" if x11 else "wayland"
        with (output / "spectacle.log").open("a") as log:
            subprocess.run(["spectacle", "--background", "--nonotify", "--fullscreen",
                            "--output", str(output / name)], env=capture_env, check=True,
                           timeout=15, stdout=log, stderr=subprocess.STDOUT)
        assert (output / name).is_file(), "Screenshot failed"

    try:
        if x11:
            with (output / "display").open("w") as display, (output / "xvfb.log").open("w") as log:
                xserver = subprocess.Popen(["Xvfb", "-displayfd", "1", "-screen", "0", "960x640x24", "-nolisten", "tcp"], stdout=display, stderr=log)
            number = wait_for(lambda: (output / "display").read_text().strip())
            assert number.isdigit(), "Invalid private X display"
            os.environ["DISPLAY"] = ":" + number
            os.environ["QT_QPA_PLATFORM"] = "xcb"
        command = [str(output / "bin/kwin_x11"), "--no-kactivities"] if x11 else [
                str(output / "bin/kwin_wayland"), "--virtual",
                *(["--xwayland"] if os.environ["MTTKDE_CAPTURE_BACKEND"] == "xcb" else []),
                "--scale", os.environ["MTTKDE_CAPTURE_SCALE"],
                "--width", "960", "--height", "640", "--no-lockscreen",
                "--no-global-shortcuts", "--no-kactivities",
                "--exit-with-session", shlex.join([sys.executable, script, "--session"])]
        with (output / "kwin.log").open("w") as log:
            kwin = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        if x11:
            def ready():
                return subprocess.run(["qdbus6", "org.kde.KWin", "/KWin", "org.kde.KWin.supportInformation"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5).returncode == 0
            wait_for(ready)
            env = dict(os.environ)
        else:
            wait_for(lambda: (output / "session-env.json").exists())
            env = json.loads((output / "session-env.json").read_text())
        assert_compositor_owner(kwin.pid)
        if os.environ.get("MTTKDE_CAPTURE_CONFLICTS"):
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/scripts"))
            from steps import acrylic_glass as installer_glass
            competitor = os.environ["MTTKDE_CAPTURE_CONFLICT_EFFECT"]
            assert competitor in installer_glass.CONFLICTING_BLURS
            assert installer_glass.kw_write("--file", "kwinrc", "--group", "Plugins", "--key", competitor + "Enabled", "true")
            dbus("/Effects", "org.kde.kwin.Effects.loadEffect", competitor)
            assert competitor in installer_glass._loaded_effects(), "Control blur did not load"
            assert installer_glass._disable_conflicting_blurs(), "Installer conflict handoff failed"
            saved_conflicts = installer_glass._conflict_state_path().read_bytes()
            assert not installer_glass._loaded_effects().intersection(installer_glass.CONFLICTING_BLURS)
            assert installer_glass._disable_conflicting_blurs(), "Reinstall handoff failed"
            assert installer_glass._conflict_state_path().read_bytes() == saved_conflicts
        env["QT_QPA_PLATFORM"] = "xcb" if x11 else "wayland"
        # The virtual backend's --scale can change pixel dimensions while
        # leaving the output at 1x. Set and verify the actual compositor scale.
        scale = float(os.environ["MTTKDE_CAPTURE_SCALE"])
        if not x11:
            outputs = json.loads(subprocess.check_output(
                ["kscreen-doctor", "-j"], env=env, text=True, timeout=10))["outputs"]
            output_name = outputs[0]["name"]
            subprocess.run(["kscreen-doctor", f"output.{output_name}.scale.{scale:g}"],
                           env=env, check=True, timeout=10, stdout=subprocess.DEVNULL)
            outputs = json.loads(subprocess.check_output(
                ["kscreen-doctor", "-j"], env=env, text=True, timeout=10))["outputs"]
            assert any(output["name"] == output_name and output["scale"] == scale
                       for output in outputs), "Virtual output scale was not applied"
        with (output / "clients.log").open("w") as log:
            if not os.environ.get("MTTKDE_CAPTURE_DESKTOP"):
                background = subprocess.Popen([sys.executable, script, "--client", "desktop",
                                               "-name", "capture-desktop"], env=env,
                                              stdout=log, stderr=subprocess.STDOUT)
            time.sleep(1)
            vm_env = env | {"QT_QPA_PLATFORM": os.environ["MTTKDE_CAPTURE_BACKEND"]}
            app_command = [sys.executable, script, "--client", "vm", "-name", os.environ["MTTKDE_CAPTURE_IDENTITY"]]
            if os.environ.get("MTTKDE_CAPTURE_APPLICATION") == "nautilus":
                app_command = ["nautilus", "--new-window", str(output / "home")]
                vm_env.update(GDK_BACKEND="x11" if os.environ["MTTKDE_CAPTURE_BACKEND"] == "xcb" else "wayland", GSK_RENDERER="gl")
            vm = subprocess.Popen(app_command,
                                  env=vm_env, stdout=log, stderr=subprocess.STDOUT)
        time.sleep(1)
        dbus("/Effects", "org.kde.kwin.Effects.unloadEffect", effect)
        capture("effect-off.png")
        loaded = dbus("/Effects", "org.kde.kwin.Effects.loadEffect", effect)
        active = dbus("/Effects", "org.kde.kwin.Effects.activeEffects")
        if effect == "liquidglass":
            assert dbus("/Effects", "org.kde.kwin.Effects.debug", "liquidglass", "status") == "ready", "Glass shaders did not initialize"
        (output / "support.txt").write_text(dbus("/KWin", "org.kde.KWin.supportInformation"))
        (output / "effects.txt").write_text(dbus("/Effects", "org.kde.kwin.Effects.listOfEffects"))
        plugin_loads = [line for line in (output / "kwin.log").read_text().splitlines()
                       if f"{effect}.so" in line and '" loaded library' in line]
        plugin = output / f"plugins/{plugin_family}/effects/plugins/{effect}.so"
        mappings = [line for line in Path(f"/proc/{kwin.pid}/maps").read_text().splitlines()
                    if f"/{effect}.so" in line]
        assert mappings and all(
            line.split(maxsplit=5)[5] == str(plugin)
            and int(line.split()[4]) == plugin.stat().st_ino for line in mappings
        ), "KWin must map this probe's exact plugin inode"
        (output / "evidence.json").write_text(json.dumps({
            "loaded": loaded, "active_effects": active, "plugin_loads": plugin_loads,
            "plugin_mappings": mappings,
            "dbus_owner_verified": True, "kwin_pid": kwin.pid,
            "identity": os.environ["MTTKDE_CAPTURE_IDENTITY"],
            "client_backend": os.environ["MTTKDE_CAPTURE_BACKEND"], "scale": os.environ["MTTKDE_CAPTURE_SCALE"],
            "compositor_backend": "x11" if x11 else "wayland",
            "capture_backend": os.environ["MTTKDE_CAPTURE_SCREENSHOT_API"],
            "plugin_sha256": hashlib.sha256(plugin.read_bytes()).hexdigest(),
            "kwin_version": subprocess.check_output(
                [command[0], "--version"], text=True, timeout=5).strip(),
        }, indent=2))
        assert loaded == "true" and effect in active.splitlines(), "Effect did not activate"
        assert vm.poll() is None and (background is None or background.poll() is None), "Test client exited"
        capture("effect-on.png")
        if os.environ.get("MTTKDE_CAPTURE_WOBBLY"):
            # All input targets the private Xvfb display, after verifying its
            # compositor owner above. Never inherit the user's DISPLAY/bus.
            assert x11 and dbus("/Effects", "org.kde.kwin.Effects.loadEffect", "wobblywindows") == "true"
            def xdo(*args):
                return subprocess.check_output(["xdotool", *args], env=env, text=True, timeout=10).strip()
            window_id = xdo("search", "--name", "^Synthetic VM surface$").splitlines()[0]
            xdo("windowactivate", "--sync", window_id)
            xdo("windowmove", window_id, "180", "140")
            before = xdo("getwindowgeometry", "--shell", window_id)
            capture("wobbly-rest.png")
            xdo("mousemove", "420", "280", "keydown", "Alt_L", "mousedown", "1")
            try:
                # Keep the model moving while the screenshot service captures.
                import threading
                done = threading.Event()
                def motion():
                    for x in [450, 510, 570, 510, 450, 390] * 5:
                        if done.is_set():
                            break
                        xdo("mousemove", str(x), "310")
                        time.sleep(.04)
                thread = threading.Thread(target=motion)
                thread.start()
                try:
                    time.sleep(.12)
                    assert "wobblywindows" in dbus("/Effects", "org.kde.kwin.Effects.activeEffects").splitlines(), "Move did not activate Wobbly Windows"
                    capture("wobbly-moving.png", delay=0)
                finally:
                    done.set()
                    thread.join(timeout=10)
            finally:
                xdo("mouseup", "1", "keyup", "Alt_L")
            capture("wobbly-settled.png", delay=2)
            after = xdo("getwindowgeometry", "--shell", window_id)
            assert before != after, "The isolated window did not move"
            assert dbus("/Effects", "org.kde.kwin.Effects.debug", "liquidglass", "status") == "ready"
            (output / "wobbly.json").write_text(json.dumps({"before": before, "after": after,
                "active_during_motion": True, "shader_status": "ready"}, indent=2))
        if os.environ.get("MTTKDE_CAPTURE_DAMAGE"):
            (output / "damage-trigger").touch()
            capture("partial-update.png")
            dbus("/KWin", "org.kde.KWin.reconfigure")
            capture("full-repaint.png")
        if os.environ.get("MTTKDE_CAPTURE_CONFLICTS"):
            installer_glass._restore_conflicting_blurs()
            assert installer_glass._conflict_state_path().read_bytes() == saved_conflicts
            assert competitor not in installer_glass._loaded_effects(), "Recovery enabled competing blur while Acrylic Glass was active"
            dbus("/Effects", "org.kde.kwin.Effects.unloadEffect", effect)
            installer_glass._restore_conflicting_blurs()
            assert installer_glass._plugin_setting(competitor) == "true"
            assert not installer_glass._conflict_state_path().exists()
            wait_for(lambda: competitor in (installer_glass._loaded_effects() or set()))
            (output / "conflicts.json").write_text(json.dumps({"competitor": competitor, "handoff": True, "reinstall": True, "active_recovery_guard": True, "restored": True}, indent=2))
        if os.environ.get("MTTKDE_CAPTURE_COMPANION"):
            assert dbus("/Effects", "org.kde.kwin.Effects.loadEffect", "liquidglass") == "true"
            assert "liquidglass" in dbus("/Effects", "org.kde.kwin.Effects.activeEffects").splitlines()
            companion = output / "plugins/kwin/effects/plugins/liquidglass.so"
            mappings = [line for line in Path(f"/proc/{kwin.pid}/maps").read_text().splitlines()
                        if "/liquidglass.so" in line]
            assert mappings and all(line.split(maxsplit=5)[5] == str(companion)
                                    and int(line.split()[4]) == companion.stat().st_ino for line in mappings)
            (output / "companion.json").write_text(json.dumps({
                "plugin_mappings": mappings, "sha256": hashlib.sha256(companion.read_bytes()).hexdigest(),
                "active": True}, indent=2))
            capture("combined.png")
            dbus("/Effects", "org.kde.kwin.Effects.unloadEffect", "liquidglass")
            capture("restored.png")
    finally:
        stop(vm)
        stop(background)
        stop(kwin)
        stop(xserver)


def run(plugin, output, scale, expected, backend, identity, renderer="software", shader_dir=None, companion=None, desktop_surface=False, squircle_blend=0.0, decoration_blur=True, backing_tint=False, appearance="light", compositor="wayland", conflicts=False, screenshot_api="spectacle", damage=False, conflict_effect="blur", application="synthetic", material=None, wobbly=False):
    assert not wobbly or (compositor == "x11" and application == "synthetic" and not shader_dir), "Wobbly probe requires native X11 synthetic client"
    assert not conflicts or not shader_dir, "Conflict probe requires Acrylic Glass"
    if compositor == "x11":
        assert screenshot_api == "spectacle", "Direct screenshot API is Wayland only"
        assert scale == 1 and not shader_dir and not companion, "X11 probe requires unscaled Acrylic Glass"
        backend = "xcb"
    effect = "kwin4_effect_shapecorners" if shader_dir else "liquidglass"
    output.mkdir(parents=True, exist_ok=False)
    for subdir in ("home", "config", "data", "cache"):
        (output / subdir).mkdir(mode=0o700)
    (output / "bin").mkdir()
    # copyfile does not carry the system binary's cap_sys_nice xattr.
    # Qt can then honor this private QT_PLUGIN_PATH without privileges.
    kwin_binary = "kwin_x11" if compositor == "x11" else "kwin_wayland"
    kwin_copy = output / "bin" / kwin_binary
    shutil.copyfile(shutil.which(kwin_binary), kwin_copy)
    kwin_copy.chmod(0o755)
    plugin_family = "kwin-x11" if compositor == "x11" else "kwin"
    dest = output / f"plugins/{plugin_family}/effects/plugins/{effect}.so"
    dest.parent.mkdir(parents=True)
    shutil.copy2(plugin, dest)
    if companion:
        assert shader_dir, "The companion probe requires Rounded Corners"
        shutil.copy2(companion, dest.parent / "liquidglass.so")
    if shader_dir:
        shaders = output / "data/kwin/shaders"
        shaders.mkdir(parents=True)
        for name in ("shapecorners.frag", "shapecorners_core.frag"):
            shutil.copyfile(shader_dir / name, shaders / name)
    (output / "config/kwinrc").write_text(
        "[Compositing]\nBackend=OpenGL\n[Plugins]\nliquidglassEnabled=false\n"
        "blurEnabled=false\nkwin4_effect_shapecornersEnabled=false\n"
        f"[Effect-liquidglass]\nBlurStrength=3.5\nBlurDecorations={str(decoration_blur).lower()}\nBackingTint={int(backing_tint)}\n"
        "BlurMatching=false\nNoiseStrength=0\nWindowCornerRadius=22\n"
        # A retired opacity value must not suppress the rendered material.
        "MaterialOpacity=0\n")
    if wobbly:
        with (output / "config/kwinrc").open("a") as config:
            config.write("[MouseBindings]\nCommandAllKey=Alt\nCommandAll1=Move\n")
    color = "32,32,32" if appearance == "dark" else "245,245,245"
    (output / "config/kdeglobals").write_text(f"[Colors:Window]\nBackgroundNormal={color}\n")
    if material:
        presets = json.loads((Path(__file__).resolve().parents[1] / "src/offline/kwin-effects/acrylic-glass/src/presets.json").read_text())
        preset = next(item for item in presets if item["id"] == material)
        with (output / "config/kwinrc").open("a") as config:
            config.write("[Effect-liquidglass]\n")
            for key, value in preset["values"].items():
                config.write(f"{key}={str(value).lower() if isinstance(value, bool) else value}\n")
    if application == "nautilus":
        assert not shader_dir and not damage, "Application probe requires Acrylic Glass without synthetic damage"
        gtk = Path(__file__).resolve().parents[1] / "src/offline/gtk" / ("MacTahoeLiquidKde-" + appearance.title()) / "gtk-4.0"
        shutil.copytree(gtk, output / "config/gtk-4.0")
        (output / "config/gtk-4.0/settings.ini").write_text(f"[Settings]\ngtk-application-prefer-dark-theme={str(appearance == 'dark').lower()}\n")
    if shader_dir:
        with (output / "config/kwinrc").open("a") as config:
            config.write(
                "[Windows]\nPlacement=Centered\n"
                "[org.kde.kdecoration2]\nBorderSize=None\nBorderSizeAuto=false\n"
                "[Round-Corners]\nSize=28\nInactiveCornerRadius=28\n"
                "UseSquircleShape=false\nUseNativeDecorationShadows=false\n"
                "AnimationDuration=0\nOutlineThickness=3\nInactiveOutlineThickness=3\n"
                "OutlineColor=255,0,0\nInactiveOutlineColor=255,0,0\n"
                "ActiveOutlineUsePalette=false\nInactiveOutlineUsePalette=false\n"
                "ActiveOutlineUseCustom=true\nInactiveOutlineUseCustom=true\n"
                "SecondOutlineThickness=0\nInactiveSecondOutlineThickness=0\n")
    if squircle_blend:
        assert shader_dir and 0.0 <= squircle_blend <= 1.0
        with (output / "config/kwinrc").open("a") as config:
            config.write(f"[Round-Corners]\nUseSquircleShape=true\nSquircleness={squircle_blend}\n")
    if desktop_surface:
        assert backend == "xcb" and shader_dir and not companion
        with (output / "config/kwinrc").open("a") as config:
            config.write("[Round-Corners]\nInclusions=" + identity + "\n")
    if companion:
        with (output / "config/kwinrc").open("a") as config:
            config.write("[Effect-liquidglass]\nNoiseStrength=16\n"
                         "[Round-Corners]\nOutlineThickness=0\nInactiveOutlineThickness=0\n"
                         "ShadowSize=0\nInactiveShadowSize=0\n")
    env = {key: value for key, value in os.environ.items()
           if key in ("PATH", "LANG", "LC_ALL", "USER", "LOGNAME")}
    # UNIX sockets have a 108-byte path limit; repository paths may be longer.
    runtime = tempfile.TemporaryDirectory(prefix="mttcap-")
    env.update(HOME=str(output / "home"), XDG_CONFIG_HOME=str(output / "config"),
               XDG_SESSION_TYPE=compositor, XDG_CURRENT_DESKTOP="KDE",
               XDG_DATA_HOME=str(output / "data"), XDG_CACHE_HOME=str(output / "cache"),
               XDG_RUNTIME_DIR=runtime.name, QT_PLUGIN_PATH=str(output / "plugins"),
               QT_QPA_PLATFORM="offscreen", QT_DEBUG_PLUGINS="1", XCURSOR_SIZE="24",
               QT_FORCE_STDERR_LOGGING="1", QT_LOGGING_RULES="kwin_*.debug=true;qt.core.plugin.*.debug=true",
               LIBGL_ALWAYS_SOFTWARE="1" if renderer == "software" else "0", KWIN_COMPOSE="O2",
               MTTKDE_CAPTURE_DIR=str(output), MTTKDE_CAPTURE_SCALE=str(scale),
               MTTKDE_CAPTURE_BACKEND=backend, MTTKDE_CAPTURE_IDENTITY=identity,
               MTTKDE_CAPTURE_COMPOSITOR=compositor,
               MTTKDE_CAPTURE_CONFLICTS="1" if conflicts else "",
               MTTKDE_CAPTURE_CONFLICT_EFFECT=conflict_effect,
               MTTKDE_CAPTURE_APPLICATION=application,
               MTTKDE_CAPTURE_WOBBLY="1" if wobbly else "",
               MTTKDE_CAPTURE_SCREENSHOT_API=screenshot_api,
               MTTKDE_CAPTURE_DAMAGE="1" if damage else "",
               MTTKDE_CAPTURE_DESKTOP="1" if desktop_surface else "", MTTKDE_CAPTURE_EFFECT=effect, MTTKDE_CAPTURE_COMPANION="1" if companion else "")
    command = ["dbus-run-session", "--", sys.executable, str(Path(__file__).resolve()),
               "--inside", str(output)]
    if wobbly:
        # llvmpipe disables animations by default; enable only this private compositor.
        env["KWIN_EFFECTS_FORCE_ANIMATIONS"] = "1"
    if screenshot_api == "dbus":
        # Restricted to the private compositor spawned with this environment.
        env["KWIN_SCREENSHOT_NO_PERMISSION_CHECKS"] = "1"
    # Screenshot authorization on older KWin uses the desktop-entry cache.
    # Build it in this probe's private HOME/cache, never the user's session.
    if shutil.which("kbuildsycoca6"):
        menus = output / "config/menus"
        menus.mkdir()
        (menus / "applications.menu").write_text(
            '<!DOCTYPE Menu PUBLIC "-//freedesktop//DTD Menu 1.0//EN" '
            '"http://www.freedesktop.org/standards/menu-spec/1.0/menu.dtd">'
            '<Menu><Name>Applications</Name><DefaultAppDirs/>'
            '<Include><All/></Include></Menu>')
        with (output / "sycoca.log").open("w") as log:
            subprocess.run(["kbuildsycoca6", "--noincremental"], env=env,
                           check=True, timeout=30, stdout=log, stderr=subprocess.STDOUT)
    process = subprocess.Popen(command, env=env, start_new_session=True)
    try:
        if process.wait(timeout=60):
            raise RuntimeError("Isolated compositor capture failed; inspect logs")
    finally:
        # Kill only this invocation's private process group, also on timeout.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        stop(process)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        runtime.cleanup()
    if desktop_surface:
        from PIL import Image, ImageChops
        original = Image.open(output / "effect-off.png").convert("RGB")
        rendered = Image.open(output / "effect-on.png").convert("RGB")
        assert original.getcolors(original.width * original.height) and sum(
            count for count, color in original.getcolors(original.width * original.height)
            if color == (55, 120, 170)) > 30000, "Desktop surface missing"
        passed = ImageChops.difference(original, rendered).getbbox() is None
        (output / "pixels.json").write_text(json.dumps({"desktop_unchanged": passed}) + "\n")
        assert passed, "ShapeCorners changed a desktop surface"
    elif companion:
        compare_corners(output)
    elif shader_dir:
        compare_outline(output)
    elif wobbly:
        compare_wobbly(output)
    elif application == "nautilus":
        from PIL import Image, ImageChops
        before = Image.open(output / "effect-off.png").convert("RGB")
        after = Image.open(output / "effect-on.png").convert("RGB")
        difference = ImageChops.difference(before, after)
        changed = sum(any(pixel) for pixel in zip(*[iter(difference.tobytes())] * 3))
        assert len(before.getcolors(before.width * before.height)) > 100, "Application capture is blank"
        passed = changed == 0 if expected == "unchanged" else changed > 1000
        (output / "pixels.json").write_text(json.dumps({"application": application, "expected": expected, "changed_pixels": changed, "passed": passed}, indent=2))
        assert passed, "Application glass pixel comparison failed"
    else:
        compare(output, expected)
    if damage:
        from PIL import Image, ImageChops
        initial = Image.open(output / "effect-on.png").convert("RGB")
        partial = Image.open(output / "partial-update.png").convert("RGB")
        reference = Image.open(output / "full-repaint.png").convert("RGB")
        assert ImageChops.difference(initial, reference).getbbox(), "Backdrop update was not visible"
        diff = ImageChops.difference(partial, reference)
        mismatch = sum(any(pixel) for pixel in zip(*[iter(diff.tobytes())] * 3))
        (output / "damage.json").write_text(json.dumps({"mismatched_pixels": mismatch, "passed": mismatch == 0}, indent=2))
        assert mismatch == 0, "Partial damage differs from a full repaint"


def compare_corners(output):
    """Glass and grain must not fill the pixels removed by ShapeCorners."""
    from PIL import Image
    images = [Image.open(output / name).convert("RGB") for name in
              ("effect-off.png", "effect-on.png", "combined.png", "restored.png")]
    original, rounded, combined, restored = images
    blue = (55, 120, 170)
    background = {(33, 66, 99), (225, 199, 135)}
    cutouts = [(x, y) for y in range(original.height) for x in range(original.width)
               if original.getpixel((x, y)) == blue and rounded.getpixel((x, y)) in background]
    assert len(cutouts) > 20, "Rounded corner cutouts were not visible"
    changed = sum(combined.getpixel(p) != rounded.getpixel(p) for p in cutouts)
    assert all(restored.getpixel(p) == rounded.getpixel(p) for p in cutouts), "Unload did not restore corners"
    body = [(x, y) for y in range(original.height) for x in range(original.width)
            if original.getpixel((x, y)) == blue]
    left, right = min(x for x, y in body), max(x for x, y in body)
    top, bottom = min(y for x, y in body), max(y for x, y in body)
    center_changes = sum(combined.getpixel((x, y)) != rounded.getpixel((x, y))
                         for y in range(top + (bottom-top)//3, top + 2*(bottom-top)//3)
                         for x in range(left + (right-left)//3, left + 2*(right-left)//3))
    assert center_changes > 100, "Glass was not visibly rendered inside the translucent client"
    metrics = {"cutout_pixels": len(cutouts), "leaked_pixels": changed,
               "interior_changed_pixels": center_changes, "passed": changed == 0}
    (output / "pixels.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics))
    assert metrics["passed"], "Glass or grain leaked outside the rounded window"


def compare_outline(output):
    from PIL import Image

    def bounds(path, matches):
        with Image.open(path).convert("RGB") as image:
            points = [(x, y) for y in range(image.height) for x in range(image.width)
                      if matches(image.getpixel((x, y)))]
        assert points, f"Test surface or outline missing in {path}"
        return (min(x for x, y in points), min(y for x, y in points),
                max(x for x, y in points), max(y for x, y in points))

    client = bounds(output / "effect-off.png", lambda p: p == (55, 120, 170))
    outline = bounds(output / "effect-on.png", lambda p: p[0] > 230 and p[1] < 20 and p[2] < 20)
    assert client[2] - client[0] > 400, "Test window is not mapped at its expected size"
    delta = outline[3] - client[3]
    metrics = {"client_bounds": client, "outline_bounds": outline,
               "bottom_offset": delta, "passed": abs(delta) <= 4}
    (output / "pixels.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics))
    assert metrics["passed"], "Rounded outline is displaced from the window bottom"


def compare_wobbly(output):
    from PIL import Image
    reference_colors = ((33, 66, 99), (225, 199, 135), (55, 120, 170))
    metrics = {}
    for name in ("rest", "moving", "settled"):
        image = Image.open(output / f"wobbly-{name}.png").convert("RGB")
        pixels = iter(image.tobytes())
        # Sharp backdrop tiles and the opaque client patch are not glass.
        # Antialiased edges alone cannot meet this interior-area threshold.
        glass = sum(all(max(abs(a - b) for a, b in zip(pixel, color)) > 12
                        for color in reference_colors)
                    for pixel in zip(pixels, pixels, pixels))
        metrics[name] = {"glass_pixels": glass, "passed": glass > 10000}
    (output / "wobbly-pixels.json").write_text(json.dumps(metrics, indent=2) + "\n")
    assert all(item["passed"] for item in metrics.values()), "Glass disappeared during Wobbly motion: " + str(metrics)


def compare(output, expected):
    from collections import Counter
    from PIL import Image, ImageChops

    with Image.open(output / "effect-off.png") as image:
        baseline = image.convert("RGB")
    with Image.open(output / "effect-on.png") as image:
        rendered = image.convert("RGB")
    assert baseline.size == rendered.size
    area = baseline.width * baseline.height

    def pixels(image):
        # Avoid Pillow's deprecated getdata while supporting older distros.
        channel = iter(image.tobytes())
        return zip(channel, channel, channel)

    histogram = Counter(pixels(baseline))
    # Reject blank captures or an unmapped guest/background before comparing.
    assert histogram[(55, 120, 170)] > area / 12, "Guest rectangle missing"
    assert histogram[(33, 66, 99)] > area / 4, "Dark background tiles missing"
    assert histogram[(225, 199, 135)] > area / 4, "Light background tiles missing"
    difference = ImageChops.difference(baseline, rendered)
    changed = sum(pixel != (0, 0, 0) for pixel in pixels(difference))
    passed = changed == 0 if expected == "unchanged" else changed > area / 2
    metrics = {"expected": expected, "changed_pixels": changed,
               "total_pixels": area, "passed": passed}
    (output / "pixels.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics))
    assert passed, "Pixel comparison failed"


if __name__ == "__main__":
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--scale", type=float, choices=(1, 1.25, 1.5, 1.75, 2), default=1)
    parser.add_argument("--identity", default="VirtualBoxVM")
    parser.add_argument("--no-decoration-blur", action="store_true")
    parser.add_argument("--backing-tint", action="store_true")
    parser.add_argument("--appearance", choices=("light", "dark"), default="light")
    parser.add_argument("--backend", choices=("wayland", "xcb"), default="wayland")
    parser.add_argument("--compositor", choices=("wayland", "x11"), default="wayland")
    parser.add_argument("--conflicts", action="store_true", help="Exercise installer handoff/reinstall/recovery against live built-in blur")
    parser.add_argument("--screenshot-api", choices=("spectacle", "dbus"), default="spectacle")
    parser.add_argument("--conflict-effect", choices=("blur", "glass", "glass_x11", "forceblur", "forceblur_x11", "better_blur_dx", "better_blur_dx_woapi"), default="blur")
    parser.add_argument("--application", choices=("synthetic", "nautilus"), default="synthetic")
    parser.add_argument("--material", choices=("tahoe", "golden-gate"))
    parser.add_argument("--wobbly", action="store_true", help="Exercise moving glass in isolated X11; requires xdotool and xprop")
    parser.add_argument("--damage", action="store_true", help="Compare a partial backdrop update against a full repaint")
    parser.add_argument("--renderer", choices=("software", "hardware"), default="software")
    parser.add_argument("--expect", choices=("unchanged", "changed"), default="unchanged")
    parser.add_argument("--rounded-shaders", type=Path, help="Test Rounded Corners using these built shaders")
    parser.add_argument("--squircle-blend", type=float, choices=(0.0, 0.55, 1.0), default=0.0)
    parser.add_argument("--desktop-surface", action="store_true", help="Probe an Xwayland desktop window, including forced inclusions")
    parser.add_argument("--companion-plugin", type=Path, help="Also test Acrylic Glass with Rounded Corners")
    parser.add_argument("--inside", type=Path)
    parser.add_argument("--session", action="store_true")
    parser.add_argument("--client", choices=("desktop", "vm"))
    args, _qt_args = parser.parse_known_args()
    if args.client:
        client(args.client)
    elif args.session:
        session()
    elif args.inside:
        inside(args.inside)
    elif args.plugin and args.output:
        run(args.plugin.resolve(), args.output.resolve(), args.scale, args.expect, args.backend, args.identity, args.renderer,
            args.rounded_shaders.resolve() if args.rounded_shaders else None,
            args.companion_plugin.resolve() if args.companion_plugin else None, args.desktop_surface, args.squircle_blend,
            not args.no_decoration_blur, args.backing_tint, args.appearance, args.compositor, args.conflicts, args.screenshot_api, args.damage, args.conflict_effect, args.application, args.material, args.wobbly)
    else:
        parser.error("--plugin and --output required")
