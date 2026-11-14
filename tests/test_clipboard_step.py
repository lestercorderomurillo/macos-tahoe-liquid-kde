"""Clipboard installer step: opt-in wiring, install/uninstall lifecycle, shortcut hand-over.

No live session needed: external tools and the compiled service are stubbed.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest


@pytest.fixture
def step(tmp_path, monkeypatch):
    from steps import clipboard as cb

    home = tmp_path / "home"
    data = home / ".local/share"
    monkeypatch.setattr(cb, "HOME", home)
    monkeypatch.setattr(cb, "BIN_DIR", home / ".local/bin")
    monkeypatch.setattr(cb, "DAEMON_DEST", home / ".local/bin/mac-tahoe-clipd")
    monkeypatch.setattr(cb, "LAUNCHER_DEST", home / ".local/bin/mac-tahoe-clipboard")
    monkeypatch.setattr(cb, "APP_DIR", data / "mac-tahoe-liquid-kde")
    monkeypatch.setattr(cb, "POPUP_DEST", data / "mac-tahoe-liquid-kde/clipboard.py")
    monkeypatch.setattr(cb, "HISTORY_DIR", data / "mac-tahoe-liquid-kde/clipboard")
    monkeypatch.setattr(cb, "DESKTOP_DEST", data / "applications/mac-tahoe-clipboard.desktop")
    monkeypatch.setattr(cb, "AUTOSTART_DEST", home / ".config/autostart/mac-tahoe-clipd.desktop")

    build = tmp_path / "build"
    build.mkdir()
    (build / "mac-tahoe-clipd").write_bytes(b"\x7fELF-fake-daemon")
    monkeypatch.setattr(cb, "BUILD", build)
    src = tmp_path / "src"
    src.mkdir()
    (src / "clipboard.py").write_text("# popup\n")
    monkeypatch.setattr(cb, "SRC", src)

    calls: list[list[str]] = []

    class Result:
        returncode = 0

    monkeypatch.setattr(cb, "have", lambda tool: True)
    monkeypatch.setattr(cb, "run_user", lambda cmd, **kw: (calls.append(list(cmd)), Result())[1])
    monkeypatch.setattr(cb, "kw_write", lambda *a: (calls.append(["kw_write", *a]), True)[1])
    popen: list[list[str]] = []
    monkeypatch.setattr(cb.subprocess, "Popen", lambda cmd, **kw: popen.append(list(cmd)))
    cb.calls, cb.popen = calls, popen
    return cb


def dbus_calls(cb):
    return [c for c in cb.calls if c[:1] == ["dbus-send"]]


def test_clipboard_is_opt_in_and_flag_is_recognised():
    import cli

    assert cli.DEFAULT_FEATURES["clipboard"] is False
    assert "clipboard" in cli.INSTALL_ORDER and "clipboard" in cli.FEATURE_DESC and "clipboard" in cli.ALL_FEATURES
    assert cli.parse_args(["--clipboard"]).cli_overrides == {"clipboard": True}
    assert cli.parse_args(["--no-clipboard"]).cli_overrides == {"clipboard": False}


def test_deps_cover_the_native_build():
    from steps import clipboard as cb

    tokens = {entry.partition(":")[0] for entry in cb.deps()}
    assert {"cmake", "kf6-guiaddons-cmake", "qt6-dbus-cmake", "qt6-gui-cmake"} <= tokens


def test_install_places_files_with_absolute_paths(step):
    step.install()

    assert step.DAEMON_DEST.read_bytes().startswith(b"\x7fELF")
    assert stat.S_IMODE(step.DAEMON_DEST.stat().st_mode) == 0o755
    assert stat.S_IMODE(step.LAUNCHER_DEST.stat().st_mode) == 0o755
    assert str(step.POPUP_DEST) in step.LAUNCHER_DEST.read_text()
    desktop = step.DESKTOP_DEST.read_text()
    assert f"Exec={step.LAUNCHER_DEST}" in desktop and "NoDisplay=true" in desktop and "X-KDE-Shortcuts=Meta+V" in desktop
    assert f"Exec={step.DAEMON_DEST}" in step.AUTOSTART_DEST.read_text()
    assert step.popen == [[str(step.DAEMON_DEST)]]      # started right away, not only at next login


def test_install_moves_meta_v_from_plasma_to_the_popup(step):
    step.install()

    sent = [" ".join(c) for c in dbus_calls(step)]
    assert any("doRegister" in c and step.SERVICE_ID in c for c in sent)
    freed = [c for c in sent if "setForeignShortcut" in c and "plasmashell,show-on-mouse-pos" in c]
    bound = [c for c in sent if "setForeignShortcut" in c and f"{step.SERVICE_ID},_launch" in c]
    assert freed and freed[0].endswith("array:int32:0")                       # Plasma's widget gives the key up
    assert bound and bound[0].endswith(f"array:int32:{step.META_V}")
    assert ["kw_write", "--file", "kglobalshortcutsrc", "--group", "services", "--group",
            step.SERVICE_ID, "--key", "_launch", "Meta+V"] in step.calls
    assert step.META_V == 0x10000056


def test_install_without_dbus_send_still_installs_and_warns(step, monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr(step, "have", lambda tool: tool != "dbus-send")
    monkeypatch.setattr(step, "warn", warnings.append)
    step.install()

    assert step.DAEMON_DEST.is_file()
    assert dbus_calls(step) == []
    assert any("Meta+V" in w for w in warnings)      # tells the user how to bind the key by hand


def test_install_skips_when_artifacts_are_missing(step):
    (step.BUILD / "mac-tahoe-clipd").unlink()
    step.install()

    assert not step.DAEMON_DEST.exists() and not step.DESKTOP_DEST.exists()
    assert dbus_calls(step) == []


def test_reinstall_replaces_files_atomically_and_stops_the_old_service(step):
    step.install()
    step.DAEMON_DEST.write_bytes(b"old")
    step.calls.clear()
    step.install()

    assert step.DAEMON_DEST.read_bytes().startswith(b"\x7fELF")
    assert any("org.mactahoe.Clipboard.quit" in " ".join(c) for c in dbus_calls(step))
    assert not list(step.DAEMON_DEST.parent.glob(".mac-tahoe-clipd.*"))        # no temp files left behind


def test_uninstall_restores_plasma_shortcut_and_removes_everything(step):
    step.install()
    step.HISTORY_DIR.mkdir(parents=True)
    (step.HISTORY_DIR / "index.json").write_text("[]")
    step.calls.clear()
    step.uninstall()

    for path in (step.DAEMON_DEST, step.LAUNCHER_DEST, step.POPUP_DEST, step.DESKTOP_DEST, step.AUTOSTART_DEST):
        assert not path.exists(), path
    assert not step.HISTORY_DIR.exists()
    sent = [" ".join(c) for c in dbus_calls(step)]
    assert any("org.mactahoe.Clipboard.quit" in c for c in sent)
    handed_back = [c for c in sent if "setForeignShortcut" in c and "plasmashell,show-on-mouse-pos" in c]
    assert handed_back and handed_back[0].endswith(f"array:int32:{step.META_V}")
    assert any("KGlobalAccel.unregister" in c for c in sent)


def test_uninstall_when_nothing_is_installed_is_a_quiet_noop(step):
    step.uninstall()
    step.uninstall()   # idempotent
    assert not step.DAEMON_DEST.exists()


def test_uninstall_never_follows_a_history_symlink(step, tmp_path):
    victim = tmp_path / "precious"
    victim.mkdir()
    (victim / "keep.txt").write_text("keep")
    step.HISTORY_DIR.parent.mkdir(parents=True)
    step.HISTORY_DIR.symlink_to(victim)
    step.uninstall()

    assert (victim / "keep.txt").read_text() == "keep"


def test_sources_ship_a_spdx_header_and_the_quit_slot():
    root = Path(__file__).resolve().parents[1] / "src/offline/clipboard"
    for rel in ("clipboard.py", "clipd/main.cpp", "clipd/CMakeLists.txt"):
        assert "SPDX-License-Identifier: GPL-3.0-or-later" in (root / rel).read_text(), rel
    assert "void quit()" in (root / "clipd/main.cpp").read_text()    # the uninstaller relies on it
