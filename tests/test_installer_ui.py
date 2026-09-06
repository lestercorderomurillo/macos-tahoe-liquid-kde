"""Thin-wrapper installer UI launcher tests."""

from __future__ import annotations

import json
import os
import stat

import pytest


@pytest.fixture
def installer_ui_module():
    import installer_ui
    return installer_ui



@pytest.fixture(autouse=True)
def stable_installer_language(monkeypatch):
    """A user's persisted GUI choice must not change test expectations."""
    import installer_ui
    monkeypatch.setattr(installer_ui, "get_language", lambda: "en")


def test_preview_qml_exists(repo):
    assert (repo / "src/installer/preview_installer.qml").is_file()
    assert (repo / "src/installer/InstallerWindow.qml").is_file()
    assert (repo / "src/installer/InstallerHello.png").is_file()


def test_features_window_serializes_saves_and_coalesces_latest_state(repo):
    source = (repo / "src/installer/FeaturesWindow.qml").read_text()
    save_block = source.split("function save(): void {", 1)[1].split(
        "function _runSave(): void {", 1)[0]
    run_block = source.split("function _runSave(): void {", 1)[1].split(
        "P5Support.DataSource {", 1)[0]
    saver_block = source.split("id: saver", 1)[1].split(
        "onVisibleChanged:", 1)[0]

    assert "property bool saveInFlight: false" in source
    assert "property bool savePending: false" in source
    assert save_block.index("if (saveInFlight)") < save_block.index(
        "savePending = true") < save_block.index("return")
    assert save_block.index("saveInFlight = true") < save_block.index(
        "_runSave()")

    # The deferred pass must serialize a fresh snapshot of current items,
    # not replay the payload captured by the older in-flight process.
    assert "for (let i = 0; i < items.length; ++i)" in run_block
    assert "payload[items[i].key] = items[i].enabled" in run_block
    assert saver_block.index("saveInFlight = false") < saver_block.index(
        "if (featuresWindow.savePending)")
    assert saver_block.index("savePending = false") < saver_block.index(
        "featuresWindow.save()")


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


@pytest.mark.parametrize("action", ["install", "uninstall", "preflight"])
def test_headless_command_skips_confirm_and_pins_progress_file(
        installer_ui_module, action):
    """The in-UI (background) launch MUST carry MTTKDE_NO_CONFIRM=1 — the
    install has no tty, so without it the confirm prompt's input() blocks
    forever and the progress bar never moves. It must also pin
    both private control paths to the files the bridge owns."""
    progress_file = "/tmp/mttkde-test-progress"
    cancel_file = "/tmp/mttkde-test-cancel"
    cmd = installer_ui_module.escalated_command_for_action(
        action, headless=True, progress_file=progress_file,
        cancel_file=cancel_file)
    assert "MTTKDE_NO_CONFIRM=1" in cmd
    assert f"MTTKDE_PROGRESS_FILE={progress_file}" in cmd
    assert f"MTTKDE_CANCEL_FILE={cancel_file}" in cmd


@pytest.mark.parametrize("kwargs", [
    {},
    {"progress_file": "/tmp/progress"},
    {"cancel_file": "/tmp/cancel"},
])
def test_headless_command_requires_both_private_files(
        installer_ui_module, kwargs):
    with pytest.raises(ValueError, match="requires progress and cancel files"):
        installer_ui_module.escalated_command_for_action(
            "install", headless=True, **kwargs)


def test_gui_progress_files_are_unique_private_and_user_owned(
        installer_ui_module):
    first = installer_ui_module._create_progress_file()
    second = installer_ui_module._create_progress_file()
    cancel = installer_ui_module._create_cancel_file()
    try:
        assert len({first, second, cancel}) == 3
        for path in (first, second, cancel):
            info = os.stat(path, follow_symlinks=False)
            assert os.path.dirname(path) == "/tmp"
            assert stat.S_ISREG(info.st_mode)
            assert stat.S_IMODE(info.st_mode) == 0o600
            assert info.st_uid == os.geteuid()
            assert info.st_nlink == 1
    finally:
        for path in (first, second, cancel):
            try:
                os.unlink(path)
            except OSError:
                pass


def test_cancel_writer_rejects_symlink_and_hardlink(
        installer_ui_module, tmp_path):
    victim = tmp_path / "victim"
    victim.write_text("keep")
    symlink = tmp_path / "cancel-symlink"
    hardlink = tmp_path / "cancel-hardlink"
    symlink.symlink_to(victim)
    os.link(victim, hardlink)

    assert installer_ui_module._mark_cancel_requested(str(symlink)) is False
    assert installer_ui_module._mark_cancel_requested(str(hardlink)) is False
    assert victim.read_text() == "keep"
    assert hardlink.read_text() == "keep"


def test_supervisor_refuses_pre_cancelled_run_without_launching(
        installer_ui_module, monkeypatch, tmp_path):
    progress = tmp_path / "progress"
    cancel = tmp_path / "cancel"
    progress.write_text("")
    cancel.write_text("cancel\n")
    cancel.chmod(0o600)

    def unexpected_launch(*_args, **_kwargs):
        raise AssertionError("privileged process must not launch")

    monkeypatch.setattr(installer_ui_module.subprocess, "Popen", unexpected_launch)
    monkeypatch.setattr(
        installer_ui_module, "_isolate_supervisor_process_group", lambda: True)

    assert installer_ui_module._supervise_action(
        "install", str(progress), str(cancel)) == 130


def test_supervisor_returns_real_status_on_normal_completion(
        installer_ui_module, monkeypatch, tmp_path):
    progress = tmp_path / "progress"
    cancel = tmp_path / "cancel"
    progress.write_text("")
    cancel.write_text("")
    cancel.chmod(0o600)

    class FinishedChild:
        def poll(self):
            return 7

    monkeypatch.setattr(
        installer_ui_module.subprocess, "Popen",
        lambda *_args, **_kwargs: FinishedChild(),
    )
    monkeypatch.setattr(
        installer_ui_module, "_isolate_supervisor_process_group", lambda: True)

    assert installer_ui_module._supervise_action(
        "install", str(progress), str(cancel)) == 7


def test_supervisor_waits_for_cancelled_child_and_never_reports_success(
        installer_ui_module, monkeypatch, tmp_path):
    progress = tmp_path / "progress"
    cancel = tmp_path / "cancel"
    progress.write_text("")
    cancel.write_text("")
    cancel.chmod(0o600)

    class RunningChild:
        def __init__(self):
            self.poll_calls = 0

        def poll(self):
            self.poll_calls += 1
            return 0 if self.poll_calls == 3 else None

    child = RunningChild()
    requested = iter((False, True))
    monkeypatch.setattr(
        installer_ui_module.subprocess, "Popen",
        lambda *_args, **_kwargs: child,
    )
    monkeypatch.setattr(
        installer_ui_module, "_isolate_supervisor_process_group", lambda: True)
    monkeypatch.setattr(
        installer_ui_module, "_cancel_file_requested",
        lambda _path: next(requested))
    monkeypatch.setattr(installer_ui_module.time, "sleep", lambda _delay: None)

    assert installer_ui_module._supervise_action(
        "install", str(progress), str(cancel)) == 130
    assert child.poll_calls == 3


def test_supervisor_process_group_isolated_before_escalation(
        installer_ui_module, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        installer_ui_module.os, "setsid", lambda: calls.append("setsid"))
    monkeypatch.setattr(installer_ui_module.os, "getpid", lambda: 4242)
    monkeypatch.setattr(installer_ui_module.os, "getsid", lambda _pid: 4242)

    assert installer_ui_module._isolate_supervisor_process_group() is True
    assert calls == ["setsid"]


def test_supervisor_rejects_group_leader_still_in_gui_session(
        installer_ui_module, monkeypatch):
    monkeypatch.setattr(
        installer_ui_module.os, "setsid",
        lambda: (_ for _ in ()).throw(PermissionError("group leader")),
    )
    monkeypatch.setattr(installer_ui_module.os, "getpid", lambda: 4242)
    # pgrp ownership alone does not prove controlling-terminal detachment.
    monkeypatch.setattr(installer_ui_module.os, "getpgrp", lambda: 4242)
    monkeypatch.setattr(installer_ui_module.os, "getsid", lambda _pid: 3131)

    assert installer_ui_module._isolate_supervisor_process_group() is False


def test_supervisor_refuses_to_launch_without_group_isolation(
        installer_ui_module, monkeypatch, tmp_path):
    progress = tmp_path / "progress"
    cancel = tmp_path / "cancel"
    progress.write_text("")
    cancel.write_text("")
    cancel.chmod(0o600)
    monkeypatch.setattr(
        installer_ui_module, "_isolate_supervisor_process_group", lambda: False)
    monkeypatch.setattr(
        installer_ui_module.subprocess, "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("unsafe supervisor must not launch escalation")
        ),
    )

    assert installer_ui_module._supervise_action(
        "install", str(progress), str(cancel)) == 1


@pytest.mark.parametrize("action", ["install", "uninstall", "preflight"])
def test_terminal_command_keeps_interactive_confirm(
        installer_ui_module, action):
    """The terminal launch is interactive — it must NOT auto-skip confirm."""
    cmd = installer_ui_module.escalated_command_for_action(action, headless=False)
    assert "MTTKDE_NO_CONFIRM" not in cmd


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
    # Register HOME/USER/LOGNAME so monkeypatch restores them: the
    # function writes them straight to os.environ, which would otherwise
    # leak into later tests.
    monkeypatch.setenv("HOME", os.environ.get("HOME", "/root"))
    monkeypatch.setenv("USER", os.environ.get("USER", "root"))
    monkeypatch.setenv("LOGNAME", os.environ.get("LOGNAME", "root"))

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


# ── progress file protocol ──────────────────────────────────────────────

def test_done_record_parser_requires_valid_newline_terminated_record(
        installer_ui_module):
    marker = installer_ui_module.DONE_MARKER

    assert installer_ui_module._parse_done_record(f"{marker}\t0") == 0
    assert installer_ui_module._parse_done_record(f"{marker}\t130") == 130

    # Missing/malformed codes and a final unterminated buffer must defer to
    # QProcess's actual exit status; none may be interpreted as success.
    assert installer_ui_module._parse_done_record(marker) is None
    assert installer_ui_module._parse_done_record(f"{marker}\tbad") is None
    assert installer_ui_module._parse_done_record(
        f"{marker}\t0", terminated=False) is None
    assert installer_ui_module._parse_done_record("1\tInstalling") is None


def test_quit_request_waits_for_running_install_cancellation(
        installer_ui_module):
    class FakeApp:
        def __init__(self):
            self.quit_calls = 0

        def quit(self):
            self.quit_calls += 1

    class FakeBridge:
        running = True

        def __init__(self):
            self.cancel_calls = 0

        def cancel(self):
            self.cancel_calls += 1

    app = FakeApp()
    bridge = FakeBridge()
    shutdown = {"requested": False}

    installer_ui_module._request_app_quit(app, bridge, shutdown)
    installer_ui_module._request_app_quit(app, bridge, shutdown)

    assert shutdown["requested"] is True
    assert bridge.cancel_calls == 1
    assert app.quit_calls == 0

    bridge.running = False
    installer_ui_module._request_app_quit(app, bridge, shutdown)
    assert app.quit_calls == 1


def test_bridge_defers_partial_or_malformed_done_to_process_exit(
        installer_ui_module):
    qtcore = pytest.importorskip("PyQt6.QtCore")
    app = qtcore.QCoreApplication.instance() or qtcore.QCoreApplication([])

    partial_bridge = installer_ui_module._make_installer_bridge()
    partial_codes: list[int] = []
    partial_bridge.finished.connect(partial_codes.append)
    partial_bridge._read_progress = lambda: None
    partial_bridge._line_buf = f"{installer_ui_module.DONE_MARKER}\t0"
    partial_bridge._on_proc_finished(17, qtcore.QProcess.ExitStatus.CrashExit)

    malformed_bridge = installer_ui_module._make_installer_bridge()
    malformed_codes: list[int] = []
    malformed_bridge.finished.connect(malformed_codes.append)
    malformed_bridge._read_progress = lambda: None
    malformed_bridge._handle_record(
        f"{installer_ui_module.DONE_MARKER}\tnot-an-exit-code")
    malformed_bridge._on_proc_finished(
        23, qtcore.QProcess.ExitStatus.CrashExit)

    assert app is not None
    assert partial_codes == [17]
    assert malformed_codes == [23]


def test_bridge_progress_creation_failure_is_visible_and_does_not_launch(
        installer_ui_module, monkeypatch):
    qtcore = pytest.importorskip("PyQt6.QtCore")
    app = qtcore.QCoreApplication.instance() or qtcore.QCoreApplication([])
    bridge = installer_ui_module._make_installer_bridge()
    codes: list[int] = []
    bridge.finished.connect(codes.append)

    def fail_create() -> str:
        raise OSError("no private temp file")

    monkeypatch.setattr(installer_ui_module, "_create_progress_file", fail_create)
    bridge.start("install")

    assert app is not None
    assert bridge._proc is None
    assert bridge.running is False
    assert codes == [1]
    assert "Could not create secure installer channel" in bridge.logTail()


def test_bridge_cancel_creation_failure_cleans_progress_and_does_not_launch(
        installer_ui_module, monkeypatch, tmp_path):
    qtcore = pytest.importorskip("PyQt6.QtCore")
    app = qtcore.QCoreApplication.instance() or qtcore.QCoreApplication([])
    bridge = installer_ui_module._make_installer_bridge()
    progress = tmp_path / "progress"
    progress.write_text("")

    monkeypatch.setattr(
        installer_ui_module, "_create_progress_file", lambda: str(progress))

    def fail_cancel() -> str:
        raise OSError("no private cancel token")

    monkeypatch.setattr(installer_ui_module, "_create_cancel_file", fail_cancel)
    bridge.start("install")

    assert app is not None
    assert bridge._proc is None
    assert bridge.running is False
    assert not progress.exists()
    assert "Could not create secure installer channel" in bridge.logTail()


def test_bridge_failed_to_start_finishes_and_cleans_private_channels(
        installer_ui_module, tmp_path):
    qtcore = pytest.importorskip("PyQt6.QtCore")
    app = qtcore.QCoreApplication.instance() or qtcore.QCoreApplication([])
    bridge = installer_ui_module._make_installer_bridge()
    progress = tmp_path / "progress"
    cancel = tmp_path / "cancel"
    progress.write_text("")
    cancel.write_text("")
    bridge._progress_file = str(progress)
    bridge._cancel_file = str(cancel)
    bridge._running = True
    codes: list[int] = []
    bridge.finished.connect(codes.append)

    class FailedProcess:
        @staticmethod
        def errorString():
            return "exec failed"

    bridge._proc = FailedProcess()
    bridge._on_proc_error(qtcore.QProcess.ProcessError.FailedToStart)

    assert app is not None
    assert codes == [1]
    assert bridge.running is False
    assert not progress.exists()
    assert not cancel.exists()
    assert "Could not start installer supervisor: exec failed" in bridge.logTail()


def test_bridge_cancel_marks_exact_token_and_stays_busy_until_child_exits(
        installer_ui_module, monkeypatch, tmp_path):
    qtcore = pytest.importorskip("PyQt6.QtCore")
    app = qtcore.QCoreApplication.instance() or qtcore.QCoreApplication([])
    bridge = installer_ui_module._make_installer_bridge()
    cancel = tmp_path / "cancel"
    cancel.write_text("")
    cancel.chmod(0o600)
    bridge._cancel_file = str(cancel)
    bridge._running = True

    bridge.cancel()

    assert app is not None
    assert cancel.read_text() == "cancel\n"
    assert bridge.running is True
    assert bridge.currentStep.startswith("Cancelling…")


def test_bridge_finish_removes_only_its_per_run_progress_file(
        installer_ui_module, tmp_path):
    qtcore = pytest.importorskip("PyQt6.QtCore")
    app = qtcore.QCoreApplication.instance() or qtcore.QCoreApplication([])
    bridge = installer_ui_module._make_installer_bridge()
    progress = tmp_path / "this-run"
    cancel = tmp_path / "this-run-cancel"
    unrelated = tmp_path / "another-run"
    progress.write_text("this")
    cancel.write_text("")
    unrelated.write_text("keep")
    bridge._progress_file = str(progress)
    bridge._cancel_file = str(cancel)

    bridge._finish(1)

    assert app is not None
    assert not progress.exists()
    assert not cancel.exists()
    assert unrelated.read_text() == "keep"


def test_bridge_stays_busy_until_process_exits_after_valid_done(
        installer_ui_module):
    qtcore = pytest.importorskip("PyQt6.QtCore")
    app = qtcore.QCoreApplication.instance() or qtcore.QCoreApplication([])
    bridge = installer_ui_module._make_installer_bridge()
    codes: list[int] = []
    bridge.finished.connect(codes.append)
    bridge._running = True
    bridge._read_progress = lambda: None

    bridge._handle_record(f"{installer_ui_module.DONE_MARKER}\t0")

    assert app is not None
    assert bridge.running is True
    assert bridge._exit_code is None
    assert bridge._progress_exit_code == 0
    assert codes == []

    bridge._on_proc_finished(0, qtcore.QProcess.ExitStatus.NormalExit)
    assert bridge.running is False
    assert codes == [0]


def test_nonzero_process_status_overrides_earlier_success_marker(
        installer_ui_module):
    qtcore = pytest.importorskip("PyQt6.QtCore")
    app = qtcore.QCoreApplication.instance() or qtcore.QCoreApplication([])
    bridge = installer_ui_module._make_installer_bridge()
    codes: list[int] = []
    bridge.finished.connect(codes.append)
    bridge._running = True
    bridge._read_progress = lambda: None
    bridge._handle_record(f"{installer_ui_module.DONE_MARKER}\t0")

    bridge._on_proc_finished(17, qtcore.QProcess.ExitStatus.CrashExit)

    assert app is not None
    assert codes == [17]


def test_log_step_writes_progress_records(monkeypatch, tmp_path):
    """step() mirrors each title into the progress file; reset truncates
    and done appends the terminal marker. This is the channel the UI
    reads instead of parsing stdout."""
    import importlib
    progress = tmp_path / "progress"
    progress.touch(mode=0o600)
    monkeypatch.setenv("MTTKDE_PROGRESS_FILE", str(progress))
    import log
    importlib.reload(log)
    try:
        log.progress_reset()
        log.step("Verification")
        log.step("Installing fonts")
        log.progress_done(0)

        lines = progress.read_text().splitlines()
        assert lines == ["1\tVerification", "2\tInstalling fonts", "__DONE__\t0"]
        assert stat.S_IMODE(progress.stat().st_mode) == 0o600
    finally:
        # Restore the module's default path for any later test.
        monkeypatch.delenv("MTTKDE_PROGRESS_FILE", raising=False)
        importlib.reload(log)


def test_progress_helpers_reject_hostile_symlink(monkeypatch, tmp_path):
    import importlib
    victim = tmp_path / "victim"
    victim.write_text("do not touch")
    progress = tmp_path / "progress"
    progress.symlink_to(victim)
    monkeypatch.setenv("MTTKDE_PROGRESS_FILE", str(progress))
    import log
    importlib.reload(log)
    try:
        log.progress_reset()
        log.step("Hostile symlink")
        log.progress_done(0)

        assert progress.is_symlink()
        assert victim.read_text() == "do not touch"
    finally:
        monkeypatch.delenv("MTTKDE_PROGRESS_FILE", raising=False)
        importlib.reload(log)


def test_progress_helpers_reject_foreign_owned_precreation(
        monkeypatch, tmp_path):
    import importlib
    progress = tmp_path / "progress"
    progress.write_text("untrusted")
    monkeypatch.setenv("MTTKDE_PROGRESS_FILE", str(progress))
    import log
    importlib.reload(log)
    actual_uid = os.geteuid()
    monkeypatch.setattr(log.os, "geteuid", lambda: actual_uid + 1)
    try:
        log.progress_reset()
        log.step("Wrong owner")
        log.progress_done(0)

        assert progress.read_text() == "untrusted"
    finally:
        monkeypatch.delenv("MTTKDE_PROGRESS_FILE", raising=False)
        importlib.reload(log)


def test_progress_helpers_reject_hardlinked_precreation(
        monkeypatch, tmp_path):
    import importlib
    victim = tmp_path / "victim"
    victim.write_text("do not truncate")
    progress = tmp_path / "progress"
    os.link(victim, progress)
    monkeypatch.setenv("MTTKDE_PROGRESS_FILE", str(progress))
    import log
    importlib.reload(log)
    try:
        log.progress_reset()
        log.step("Hard link")
        log.progress_done(0)

        assert victim.read_text() == "do not truncate"
        assert progress.read_text() == "do not truncate"
        assert progress.stat().st_nlink == 2
    finally:
        monkeypatch.delenv("MTTKDE_PROGRESS_FILE", raising=False)
        importlib.reload(log)


def test_progress_helpers_never_raise_on_unwritable_path(monkeypatch, tmp_path):
    """A progress-file hiccup must never abort an install."""
    import importlib
    bad = tmp_path / "nope" / "progress"  # parent dir doesn't exist
    monkeypatch.setenv("MTTKDE_PROGRESS_FILE", str(bad))
    import log
    importlib.reload(log)
    try:
        log.progress_reset()
        log.step("Verification")
        log.progress_done(1)  # must not raise
    finally:
        monkeypatch.delenv("MTTKDE_PROGRESS_FILE", raising=False)
        importlib.reload(log)


def test_configured_progress_channel_is_not_recreated_after_gui_cleanup(
        monkeypatch, tmp_path):
    """A late CLI write cannot resurrect a channel its GUI removed."""
    import importlib
    progress = tmp_path / "removed-progress"
    monkeypatch.setenv("MTTKDE_PROGRESS_FILE", str(progress))
    import log
    importlib.reload(log)
    try:
        log.progress_reset()
        log.step("Already reaped")
        log.progress_done(130)

        assert not progress.exists()
    finally:
        monkeypatch.delenv("MTTKDE_PROGRESS_FILE", raising=False)
        importlib.reload(log)


def test_unconfigured_progress_channel_is_created_lazily(monkeypatch, tmp_path):
    import log
    progress = tmp_path / "classic-progress"
    monkeypatch.setattr(log, "_CONFIGURED_PROGRESS_FILE", None)
    monkeypatch.setattr(log, "PROGRESS_FILE", str(progress))

    log.progress_reset()
    log.progress_done(0)

    assert progress.read_text().splitlines() == ["__DONE__\t0"]
    assert stat.S_IMODE(progress.stat().st_mode) == 0o600


# ── update banner ───────────────────────────────────────────────────────

def test_update_status_reports_available_when_remote_is_newer(
        installer_ui_module, monkeypatch):
    """A strictly-newer GitHub tag flips available=True. Reuses the same
    parse_semver / read_version the CLI uses, so the GUI and CLI verdicts
    can never disagree."""
    monkeypatch.setattr(installer_ui_module, "read_version", lambda: "0.20.1")
    monkeypatch.setattr(installer_ui_module, "fetch_latest_release", lambda: "0.21.0")

    status = installer_ui_module.update_status()

    assert status == {
        "current": "0.20.1",
        "latest": "0.21.0",
        "available": True,
        "reachable": True,
    }


def test_update_status_not_available_when_on_latest(
        installer_ui_module, monkeypatch):
    monkeypatch.setattr(installer_ui_module, "read_version", lambda: "0.21.0")
    monkeypatch.setattr(installer_ui_module, "fetch_latest_release", lambda: "0.21.0")

    status = installer_ui_module.update_status()

    assert status["available"] is False
    assert status["reachable"] is True


def test_update_status_unreachable_when_fetch_returns_none(
        installer_ui_module, monkeypatch):
    """Offline / rate-limited / opted-out (fetch returns None) must never
    surface a banner and must never raise."""
    monkeypatch.setattr(installer_ui_module, "read_version", lambda: "0.20.1")
    monkeypatch.setattr(installer_ui_module, "fetch_latest_release", lambda: None)

    status = installer_ui_module.update_status()

    assert status == {
        "current": "0.20.1",
        "latest": "",
        "available": False,
        "reachable": False,
    }


def test_main_check_update_emits_json(installer_ui_module, monkeypatch, capsys):
    monkeypatch.setattr(installer_ui_module, "drop_root_to_invoking_user", lambda: 0)
    monkeypatch.setattr(
        installer_ui_module,
        "update_status",
        lambda: {"current": "0.20.1", "latest": "0.21.0",
                 "available": True, "reachable": True},
    )

    rc = installer_ui_module.main(["--check-update"])
    out = capsys.readouterr().out.strip()

    assert rc == 0
    assert json.loads(out)["available"] is True


def test_launch_preview_reports_missing_pyqt6(
        installer_ui_module, monkeypatch, capsys):
    """When PyQt6 cannot be imported, launch_preview must report the
    missing dependency clearly and return 1 instead of falling through to
    a standalone qmlscene/qml launch. The QML window needs the `installer`
    context property that only the PyQt6 bridge registers, so the
    standalone harness only emits "ReferenceError: installer is not
    defined" on every binding."""
    monkeypatch.setattr(installer_ui_module, "_launch_preview_pyqt", lambda: -1)

    rc = installer_ui_module.launch_preview()
    err = capsys.readouterr().err

    assert rc == 1
    assert "PyQt6" in err
    assert "./installer" in err


def test_confirm_auto_accepts_in_no_confirm_mode(monkeypatch, capsys):
    """The anti-hang: MTTKDE_NO_CONFIRM=1 makes confirm() return True
    without ever touching the tty / stdin, so the background install
    started by the UI doesn't deadlock on input()."""
    monkeypatch.setenv("MTTKDE_NO_CONFIRM", "1")
    import cli
    assert cli.confirm("Install at your own risk.") is True
    assert "auto-accepting" in capsys.readouterr().out
