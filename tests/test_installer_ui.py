"""Thin-wrapper installer UI launcher tests."""

from __future__ import annotations

import json
import os

import pytest


@pytest.fixture
def installer_ui_module():
    import installer_ui
    return installer_ui


def test_preview_qml_exists(repo):
    assert (repo / "src/scripts/preview_installer.qml").is_file()
    assert (repo / "src/scripts/InstallerWindow.qml").is_file()
    assert (repo / "src/scripts/InstallerHello.png").is_file()


def test_repo_installer_entry_exists(repo):
    script = repo / "installer"
    assert script.is_file()
    assert script.stat().st_mode & 0o111


@pytest.mark.parametrize("action,expected", [
    ("install", "sudo ./install"),
    ("uninstall", "sudo ./uninstall"),
    ("preflight", "sudo ./install --preflight"),
])
def test_command_for_action(installer_ui_module, action, expected):
    assert installer_ui_module.command_for_action(action) == expected


def test_launch_action_prefers_first_available_terminal(
        installer_ui_module, monkeypatch, repo):
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        installer_ui_module.shutil,
        "which",
        lambda name: "/usr/bin/konsole" if name == "konsole" else None,
    )

    class DummyPopen:
        def __init__(self, argv, cwd=None, start_new_session=None):
            seen["argv"] = argv
            seen["cwd"] = cwd
            seen["start_new_session"] = start_new_session

    monkeypatch.setattr(installer_ui_module.subprocess, "Popen", DummyPopen)

    payload = installer_ui_module.launch_action("install")

    assert payload["ok"] is True
    assert payload["terminal"] == "konsole"
    assert payload["command"] == "sudo ./install"
    assert seen["argv"][:3] == ["konsole", "--noclose", "-e"]
    assert seen["argv"][-1] == f"cd {repo} && sudo ./install"
    assert seen["cwd"] == str(repo)
    assert seen["start_new_session"] is True


def test_launch_action_reports_when_no_terminal_is_available(
        installer_ui_module, monkeypatch):
    monkeypatch.setattr(installer_ui_module.shutil, "which", lambda _name: None)

    payload = installer_ui_module.launch_action("uninstall")

    assert payload["ok"] is False
    assert payload["terminal"] == ""
    assert payload["command"] == "sudo ./uninstall"
    assert "No supported terminal emulator" in payload["message"]


def test_main_launch_emits_json_payload(installer_ui_module, monkeypatch, capsys):
    monkeypatch.setattr(installer_ui_module, "drop_root_to_invoking_user", lambda: 0)
    monkeypatch.setattr(
        installer_ui_module,
        "launch_action",
        lambda action: {
            "ok": True,
            "action": action,
            "terminal": "konsole",
            "command": "sudo ./install",
            "message": "Launching sudo ./install in konsole.",
        },
    )

    rc = installer_ui_module.main(["--launch", "install"])
    out = capsys.readouterr().out.strip()

    assert rc == 0
    assert json.loads(out)["action"] == "install"


def test_drop_root_to_invoking_user_is_noop_for_regular_user(
        installer_ui_module, monkeypatch):
    monkeypatch.setattr(installer_ui_module.os, "geteuid", lambda: 1000)
    assert installer_ui_module.drop_root_to_invoking_user() == 0


def test_drop_root_to_invoking_user_requires_sudo_metadata(
        installer_ui_module, monkeypatch, capsys):
    monkeypatch.setattr(installer_ui_module.os, "geteuid", lambda: 0)
    monkeypatch.delenv("SUDO_USER", raising=False)
    monkeypatch.delenv("SUDO_UID", raising=False)
    monkeypatch.delenv("SUDO_GID", raising=False)

    rc = installer_ui_module.drop_root_to_invoking_user()
    err = capsys.readouterr().err

    assert rc == 1
    assert "regular desktop user" in err


def test_drop_root_to_invoking_user_sets_env_and_ids(
        installer_ui_module, monkeypatch, tmp_path):
    runtime_dir = tmp_path / "run/user/1000"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "bus").write_text("")

    monkeypatch.setattr(installer_ui_module.os, "geteuid", lambda: 0)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.setenv("SUDO_USER", "lester")
    monkeypatch.setenv("SUDO_UID", "1000")
    monkeypatch.setenv("SUDO_GID", "1001")

    class DummyPw:
        pw_dir = "/home/lester"

    monkeypatch.setattr(installer_ui_module.pwd, "getpwuid", lambda _uid: DummyPw())

    monkeypatch.setattr(
        installer_ui_module,
        "Path",
        lambda value: runtime_dir if value == "/run/user/1000" else __import__("pathlib").Path(value),
    )

    seen: dict[str, tuple[int, int, int]] = {}
    monkeypatch.setattr(installer_ui_module.os, "setresgid",
                        lambda r, e, s: seen.setdefault("gid", (r, e, s)))
    monkeypatch.setattr(installer_ui_module.os, "setresuid",
                        lambda r, e, s: seen.setdefault("uid", (r, e, s)))

    rc = installer_ui_module.drop_root_to_invoking_user()

    assert rc == 0
    assert os.environ["HOME"] == "/home/lester"
    assert os.environ["USER"] == "lester"
    assert os.environ["LOGNAME"] == "lester"
    assert os.environ["XDG_RUNTIME_DIR"] == str(runtime_dir)
    assert os.environ["DBUS_SESSION_BUS_ADDRESS"] == f"unix:path={runtime_dir / 'bus'}"
    assert seen["gid"] == (1001, 1001, 1001)
    assert seen["uid"] == (1000, 1000, 1000)
