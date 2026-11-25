"""RunTracker (~/.local/state/mac-tahoe-liquid-kde/last-run.json).

Focused on the write path's failure semantics: a torn or unwritable
last-run.json must be reported, not swallowed, since it's the one
place support tooling looks to see what the last install/uninstall
actually did.
"""

from __future__ import annotations

import json

import state


def test_start_writes_running_state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    tracker = state.RunTracker("install", ["--only", "fonts"])

    assert tracker.start() is True
    payload = json.loads(state.last_run_file().read_text(encoding="utf-8"))
    assert payload["status"] == "running"
    assert payload["script"] == "install"


def test_finalize_writes_completed_state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    tracker = state.RunTracker("install", [])
    tracker.start()
    tracker.mark_completed()

    assert tracker.finalize(0) is True
    payload = json.loads(state.last_run_file().read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["exit_code"] == 0


def test_write_failure_is_reported_not_swallowed(tmp_path, monkeypatch):
    """A kill/crash/disk-full mid-write must surface, not silently
    look identical to a successful run."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    warnings: list[str] = []
    monkeypatch.setattr(state, "warn", warnings.append)

    def fail_replace(_src, _dst):
        raise OSError("simulated disk full")

    monkeypatch.setattr(state.os, "replace", fail_replace)

    tracker = state.RunTracker("install", [])

    assert tracker.start() is False
    assert warnings, "a failed write must be reported, not silently swallowed"
    assert not state.last_run_file().exists()


def test_temporary_file_write_failure_is_reported(tmp_path, monkeypatch):
    """Failing before replace is distinct from an atomic rename failure."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    warnings: list[str] = []
    monkeypatch.setattr(state, "warn", warnings.append)

    real_write_text = state.Path.write_text

    def fail_temp_write(path, *args, **kwargs):
        if path.name.endswith(".tmp"):
            raise OSError("simulated write failure")
        return real_write_text(path, *args, **kwargs)

    monkeypatch.setattr(state.Path, "write_text", fail_temp_write)

    assert state.RunTracker("install", []).start() is False
    assert warnings
    assert not state.last_run_file().exists()
    assert list(state.state_dir().glob("*.tmp")) == []


def test_state_directory_creation_failure_is_reported(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    warnings: list[str] = []
    monkeypatch.setattr(state, "warn", warnings.append)

    real_mkdir = state.Path.mkdir

    def fail_state_mkdir(path, *args, **kwargs):
        if path == state.state_dir():
            raise OSError("read-only state directory")
        return real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(state.Path, "mkdir", fail_state_mkdir)

    assert state.RunTracker("install", []).start() is False
    assert warnings


def test_finalize_failure_is_reported_not_swallowed(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    tracker = state.RunTracker("install", [])
    assert tracker.start() is True

    warnings: list[str] = []
    monkeypatch.setattr(state, "warn", warnings.append)

    def fail_replace(_src, _dst):
        raise OSError("simulated disk full")

    monkeypatch.setattr(state.os, "replace", fail_replace)

    assert tracker.finalize(0) is False
    assert warnings, "a failed write must be reported, not silently swallowed"


def test_write_failure_cleans_up_temp_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(state, "warn", lambda _msg: None)

    def fail_replace(_src, _dst):
        raise OSError("simulated disk full")

    monkeypatch.setattr(state.os, "replace", fail_replace)

    tracker = state.RunTracker("install", [])
    tracker.start()

    leftovers = list(state.state_dir().glob("*.tmp")) if state.state_dir().is_dir() else []
    assert leftovers == []


def test_replace_failure_preserves_previous_run_state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    state.state_dir().mkdir(parents=True)
    state.last_run_file().write_text('{"status":"completed"}\n')
    monkeypatch.setattr(state, "warn", lambda _msg: None)
    monkeypatch.setattr(
        state.os, "replace",
        lambda _src, _dst: (_ for _ in ()).throw(OSError("disk full")),
    )

    assert state.RunTracker("install", []).start() is False
    assert state.last_run_file().read_text() == '{"status":"completed"}\n'
