"""OLED care pixel-shift service.

Engine behaviour (state machine, plasmashell reply handling), the
shipped systemd units, the installer step's flag gating, and the CLI
flag registration. The live evaluateScript round-trip needs a running
plasmashell and is only exercised on bare metal / in the VM harness.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading

import oled_care
import pytest


# ── shift patterns ────────────────────────────────────────────────────


def test_default_pattern_walks_the_requested_sequence():
    """The shipped shape: 2 px steps peaking at +8 — a 32 px top bar
    walks 32 → 34 → 36 → 38 → 40 → 38 → … and back."""
    assert oled_care.DEFAULT_MAX_SHIFT_PX == 8
    assert oled_care.SHIFT_STEP_PX == 2
    offsets, heights = oled_care.build_patterns(8)
    assert heights[:9] == [0, 2, 4, 6, 8, 6, 4, 2, 0]
    assert offsets == [0, 2, 4, 6, 8, 6, 4, 2, 0, -2, -4, -6, -8, -6, -4, -2]


def test_patterns_scale_with_max_px():
    offsets, heights = oled_care.build_patterns(4)
    assert offsets == [0, 2, 4, 2, 0, -2, -4, -2]
    assert max(offsets) == 4 and min(offsets) == -4
    assert heights == [abs(d) for d in offsets]
    assert all(h >= 0 for h in heights)


def test_max_px_is_clamped():
    assert oled_care.clamp_max_px(0) == 1
    assert oled_care.clamp_max_px(99) == oled_care.MAX_SHIFT_CEILING_PX
    assert oled_care.clamp_max_px("garbage") == oled_care.DEFAULT_MAX_SHIFT_PX
    assert oled_care.clamp_max_px(None) == oled_care.DEFAULT_MAX_SHIFT_PX


# ── script generation ─────────────────────────────────────────────────


def test_shift_script_embeds_state_and_deltas():
    script = oled_care.build_shift_script(
        {"5": {"offset": 3, "height": 32}}, 0, 0, 1, 1)
    assert '"5": {"offset": 3, "height": 32}' in script
    assert "nextOff = 1" in script and "nextH = 1" in script
    # fill panels get the height knob, everything else the offset knob
    assert 'p.lengthMode == "fill"' in script
    # the rebased base map must be printed back for persistence
    assert "print(JSON.stringify(out))" in script
    assert 'print(normalize ? "normalized" : "shifted")' in script


def test_shift_script_does_not_mutate_an_unjournaled_or_rebased_panel():
    script = oled_care.build_shift_script(
        {"5": {"offset": 3, "height": 32}}, 2, 2, 4, 4,
    )

    assert "if (!item.known || !item.matched) continue" in script
    assert "normalize ? 0 : nextH" in script
    assert "normalize ? 0 : nextOff" in script


def test_restore_script_only_undoes_our_delta():
    """Restore must compare current geometry against base + last delta —
    a panel the user moved since is left alone."""
    script = oled_care.build_restore_script(
        {"5": {"offset": 0, "height": 32}}, 2, 2)
    assert "lastOff = 2" in script and "lastH = 2" in script
    assert "p.height == base.height + lastH" in script
    assert "p.offset == base.offset + lastOff" in script


# ── state machine ─────────────────────────────────────────────────────


def _state_env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    state_home = home / ".local/state"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))
    monkeypatch.setattr(oled_care, "_PROC_ROOT", tmp_path / "no-proc")
    return state_home / "mac-tahoe-liquid-kde" / "oled-care.json"


def test_custom_xdg_state_is_migrated_to_canonical_location(
        tmp_path, monkeypatch):
    home = tmp_path / "home"
    custom = tmp_path / "plasma-state"
    proc = tmp_path / "proc"
    process = proc / "123"
    process.mkdir(parents=True)
    (process / "comm").write_text("plasmashell\n")
    (process / "environ").write_bytes(
        os.fsencode(f"XDG_STATE_HOME={custom}") + b"\0")
    legacy = custom / "mac-tahoe-liquid-kde/oled-care.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps({
        "index": 1, "last_off": 2, "last_h": 2,
        "panels": {"5": {"offset": 0, "height": 32}},
    }))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setenv("SUDO_UID", str(os.getuid()))
    monkeypatch.setattr(oled_care, "_PROC_ROOT", proc)
    monkeypatch.setattr(oled_care, "_sync_session_env_runtime_dir", lambda: None)

    expected = home / ".local/state/mac-tahoe-liquid-kde/oled-care.json"
    assert oled_care.prepare_recovery_state() is True
    assert oled_care._state_file() == expected
    assert json.loads(expected.read_text())["index"] == 1
    assert not legacy.exists()
    # Once migrated, losing the source process cannot move later invocations
    # into a different state/lock domain.
    (process / "environ").write_bytes(b"")
    assert oled_care._state_file() == expected


def test_oled_control_paths_ignore_xdg_state_changes(tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    lock_file = oled_care._operation_lock_file()
    disabled_file = oled_care._disabled_file()

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "another-state-root"))

    assert oled_care._state_file() == state_file
    assert oled_care._operation_lock_file() == lock_file
    assert oled_care._disabled_file() == disabled_file


def test_legacy_storage_without_state_or_session_fails_closed(
        tmp_path, monkeypatch):
    _state_env(tmp_path, monkeypatch)

    assert oled_care.prepare_recovery_state(
        require_known_legacy=True,
    ) is False
    assert not oled_care.canonical_storage_initialized()


def test_unknown_legacy_location_is_not_hidden_by_default_state(
        tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    state_file.parent.mkdir(parents=True)
    state_file.write_text(json.dumps({
        "index": 1, "last_off": 2, "last_h": 2,
        "panels": {"5": {"offset": 0, "height": 32}},
    }))

    # This default-path copy may be stale if an old helper later ran with a
    # custom XDG_STATE_HOME. Without a live session the installer cannot prove
    # that there is no newer custom-root recovery file.
    assert oled_care.prepare_recovery_state(
        require_known_legacy=True,
    ) is False
    assert not oled_care.canonical_storage_initialized()


def test_evaluate_script_missing_owner_is_proven_noop(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(oled_care, "_sync_session_env", lambda: False)
    monkeypatch.setattr(oled_care, "_have", lambda cmd: cmd == "qdbus6")

    def run(argv, **_kwargs):
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="false\n", stderr="")

    monkeypatch.setattr(oled_care.subprocess, "run", run)

    assert oled_care._evaluate_script("mutate()") is None
    assert len(calls) == 1 and "NameHasOwner" in calls[0][3]


def test_evaluate_script_timeout_after_dispatch_is_uncertain(monkeypatch):
    calls = 0
    monkeypatch.setattr(oled_care, "_sync_session_env", lambda: False)
    monkeypatch.setattr(oled_care, "_have", lambda cmd: cmd == "qdbus6")

    def run(argv, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return subprocess.CompletedProcess(
                argv, 0, stdout="true\n", stderr="",
            )
        raise subprocess.TimeoutExpired(argv, 15)

    monkeypatch.setattr(oled_care.subprocess, "run", run)

    assert oled_care._evaluate_script("mutate()") is oled_care._EVAL_UNCERTAIN
    assert calls == 2


def test_shift_persists_plasmashell_reply(tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    reply = json.dumps({"5": {"offset": 0, "height": 32}})
    monkeypatch.setattr(oled_care, "_evaluate_script", lambda _s: reply + "\n")

    assert oled_care.shift() == 0
    state = json.loads(state_file.read_text())
    assert state["index"] == 1
    assert state["last_off"] == 2 and state["last_h"] == 2
    assert state["panels"] == {"5": {"offset": 0, "height": 32}}


def test_rebase_fire_persists_captured_bases_at_zero_delta(
        tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    assert oled_care.save_state({
        "index": 2, "last_off": 4, "last_h": 4,
        "panels": {"5": {"offset": 0, "height": 32}},
    }) is True
    reply = "\n".join((
        json.dumps({
            "5": {"offset": 0, "height": 32},
            "9": {"offset": 7, "height": 48},
        }),
        "normalized",
    ))
    monkeypatch.setattr(oled_care, "_evaluate_script", lambda _s: reply)

    assert oled_care.shift() == 0
    state = json.loads(state_file.read_text())
    assert state == {
        "index": 0, "last_off": 0, "last_h": 0,
        "panels": {
            "5": {"offset": 0, "height": 32},
            "9": {"offset": 7, "height": 48},
        },
    }


def test_save_state_reports_and_returns_false_on_write_failure(
        tmp_path, monkeypatch, capsys):
    """A write/replace failure must not look like success — the caller
    (shift()) has already rebased on-screen panel geometry by the time
    it calls save_state(), so silently swallowing this would let the
    next timer fire resume from stale state and mis-rebase."""
    _state_env(tmp_path, monkeypatch)

    def fail_replace(_src, _dst):
        raise OSError("simulated disk full")

    monkeypatch.setattr(oled_care.os, "replace", fail_replace)

    assert oled_care.save_state({"index": 0, "last_off": 0, "last_h": 0,
                                 "panels": {}}) is False
    assert "could not save panel state" in capsys.readouterr().err
    state_dir = oled_care._state_file().parent
    assert list(state_dir.glob("*.tmp")) == []


def test_save_state_reports_temporary_file_write_failure(
        tmp_path, monkeypatch, capsys):
    _state_env(tmp_path, monkeypatch)
    real_write_text = oled_care.Path.write_text

    def fail_temp_write(path, *args, **kwargs):
        if path.name.endswith(".tmp"):
            raise OSError("simulated write failure")
        return real_write_text(path, *args, **kwargs)

    monkeypatch.setattr(oled_care.Path, "write_text", fail_temp_write)

    assert oled_care.save_state({"index": 0, "last_off": 0, "last_h": 0,
                                 "panels": {}}) is False
    assert "could not save panel state" in capsys.readouterr().err
    assert list(oled_care._state_file().parent.glob("*.tmp")) == []


def test_save_state_reports_directory_creation_failure(
        tmp_path, monkeypatch, capsys):
    _state_env(tmp_path, monkeypatch)
    real_mkdir = oled_care.Path.mkdir

    def fail_state_mkdir(path, *args, **kwargs):
        if path == oled_care._state_file().parent:
            raise OSError("read-only state directory")
        return real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(oled_care.Path, "mkdir", fail_state_mkdir)

    assert oled_care.save_state({"index": 0, "last_off": 0, "last_h": 0,
                                 "panels": {}}) is False
    assert "could not save panel state" in capsys.readouterr().err


def test_replace_failure_preserves_previous_panel_state(
        tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    state_file.parent.mkdir(parents=True)
    previous = '{"index":1,"last_off":2,"last_h":2,"panels":{}}\n'
    state_file.write_text(previous)
    monkeypatch.setattr(
        oled_care.os, "replace",
        lambda _src, _dst: (_ for _ in ()).throw(OSError("disk full")),
    )

    assert oled_care.save_state({"index": 2, "last_off": 4, "last_h": 4,
                                 "panels": {}}) is False
    assert state_file.read_text() == previous


def test_shift_save_failure_keeps_journal_without_second_plasma_call(
        tmp_path, monkeypatch):
    _state_env(tmp_path, monkeypatch)
    assert oled_care.save_state({
        "index": 1, "last_off": 2, "last_h": 2,
        "panels": {"5": {"offset": 0, "height": 32}},
    }) is True
    reply = json.dumps({"5": {"offset": 0, "height": 32}})
    scripts: list[str] = []

    def evaluate(script):
        scripts.append(script)
        return reply

    monkeypatch.setattr(oled_care, "_evaluate_script", evaluate)
    monkeypatch.setattr(oled_care, "save_state", lambda _state: False)

    assert oled_care.shift() == 1
    assert len(scripts) == 1
    assert oled_care._transition_file().is_file()
    assert oled_care._marker_state_unlocked() == oled_care._MARKER_TRANSITION


def test_shift_blocks_later_fires_after_state_save_failure(
        tmp_path, monkeypatch, capsys):
    _state_env(tmp_path, monkeypatch)
    reply = json.dumps({"5": {"offset": 0, "height": 32}})
    responses = iter((reply,))
    monkeypatch.setattr(oled_care, "_evaluate_script", lambda _s: next(responses))
    monkeypatch.setattr(oled_care, "save_state", lambda _state: False)

    assert oled_care.shift() == 1
    assert "panel recovery is pending" in capsys.readouterr().err
    assert oled_care._disabled_file().is_file()
    # The failed transition must disable the next timer fire.
    assert oled_care.shift() == 0
    with pytest.raises(StopIteration):
        next(responses)


def test_invalid_panel_map_never_commits_or_reenables_shifts(
        tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    assert oled_care.save_state({
        "index": 1, "last_off": 2, "last_h": 2,
        "panels": {"5": {"offset": 0, "height": 32}},
    }) is True
    monkeypatch.setattr(
        oled_care, "_evaluate_script",
        lambda _script: json.dumps({
            "5": {"offset": "not-an-integer", "height": 32},
        }),
    )

    assert oled_care.shift() == 1
    assert json.loads(state_file.read_text())["index"] == 1
    assert oled_care._transition_file().is_file()
    assert oled_care._marker_state_unlocked() == oled_care._MARKER_TRANSITION
    assert oled_care.enable_shifts() is False


@pytest.mark.parametrize("panel_id,base", [
    ("__proto__", {"offset": 0, "height": 32}),
    ("5", {"offset": 0, "height": 0}),
    ("5", {"offset": 1_000_001, "height": 32}),
])
def test_panel_state_rejects_unsafe_js_keys_and_implausible_geometry(
        panel_id, base):
    with pytest.raises(oled_care._StateError):
        oled_care._validate_panels({panel_id: base})


def test_uncertain_transition_restores_from_journal_before_cleanup(
        tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    prior = {
        "index": 1, "last_off": 2, "last_h": 2,
        "panels": {"5": {"offset": 0, "height": 32}},
    }
    assert oled_care.save_state(prior) is True
    with oled_care._operation_lock(1.0) as acquired:
        assert acquired
        oled_care._disable_unlocked(oled_care._MARKER_TRANSITION)
        assert oled_care._save_transition(prior, 2, 4, 4) is True
    scripts: list[str] = []
    monkeypatch.setattr(
        oled_care, "_evaluate_script",
        lambda script: scripts.append(script) or "restored-uncertain\n",
    )

    assert oled_care.restore() == 0
    assert "priorOff = 2, targetOff = 4" in scripts[0]
    assert not state_file.exists()
    assert not oled_care._transition_file().exists()
    assert not oled_care._disabled_file().exists()


def test_uncertain_restore_accepts_normalization_but_ignores_new_panels():
    script = oled_care.build_uncertain_restore_script(
        {"5": {"offset": 0, "height": 32}}, 2, 2, 4, 4,
    )

    assert "p.height == base.height ||" in script
    assert "p.offset == base.offset ||" in script
    assert "if (!base) continue" in script


def test_uncertain_first_shift_without_saved_bases_requires_manual_recovery(
        tmp_path, monkeypatch):
    _state_env(tmp_path, monkeypatch)
    empty = {"index": 0, "last_off": 0, "last_h": 0, "panels": {}}
    with oled_care._operation_lock(1.0) as acquired:
        assert acquired
        oled_care._prepare_state_unlocked()
        oled_care._disable_unlocked(oled_care._MARKER_TRANSITION)
        assert oled_care._save_transition(empty, 1, 2, 2) is True
    monkeypatch.setattr(
        oled_care, "_evaluate_script",
        lambda _script: (_ for _ in ()).throw(
            AssertionError("unknown geometry must not be guessed")
        ),
    )

    assert oled_care.restore() == 1
    assert oled_care._transition_file().is_file()
    assert oled_care._disabled_file().is_file()


def test_quiesce_waits_for_inflight_shift_then_blocks_later_shifts(
        tmp_path, monkeypatch):
    """Unlinking the helper cannot stop an exec'd cron child. The marker
    handshake must drain its transaction and make every later child a no-op.
    """
    _state_env(tmp_path, monkeypatch)
    entered = threading.Event()
    release = threading.Event()
    quiesce_started = threading.Event()
    quiesce_done = threading.Event()
    evaluated: list[str] = []
    shift_result: list[int] = []
    quiesce_result: list[bool] = []
    reply = json.dumps({"5": {"offset": 0, "height": 32}})

    def evaluate(script):
        evaluated.append(script)
        entered.set()
        assert release.wait(2)
        return reply

    monkeypatch.setattr(oled_care, "_evaluate_script", evaluate)
    shift_thread = threading.Thread(
        target=lambda: shift_result.append(oled_care.shift()))
    shift_thread.start()
    assert entered.wait(2)
    # Scheduled fires do not queue behind a long-running transition.
    assert oled_care.shift() == 0
    assert len(evaluated) == 1

    def quiesce():
        quiesce_started.set()
        quiesce_result.append(oled_care.quiesce_shifts())
        quiesce_done.set()

    quiesce_thread = threading.Thread(target=quiesce)
    quiesce_thread.start()
    assert quiesce_started.wait(2)
    assert not quiesce_done.wait(0.05)

    release.set()
    shift_thread.join(2)
    quiesce_thread.join(2)
    assert not shift_thread.is_alive() and not quiesce_thread.is_alive()
    assert shift_result == [0]
    assert quiesce_result == [True]
    assert oled_care._disabled_file().is_file()

    # A helper that reached Python after teardown sees the marker under the
    # same lock and never calls Plasma.
    assert oled_care.shift() == 0
    assert len(evaluated) == 1


def test_restore_waits_for_inflight_shift_and_consumes_its_state(
        tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    entered = threading.Event()
    release = threading.Event()
    restore_started = threading.Event()
    restore_done = threading.Event()
    scripts: list[str] = []
    shift_result: list[int] = []
    restore_result: list[int] = []
    reply = json.dumps({"5": {"offset": 0, "height": 32}})

    def evaluate(script):
        scripts.append(script)
        if "print(JSON.stringify(out))" in script:
            entered.set()
            assert release.wait(2)
            return reply
        return "restored\n"

    monkeypatch.setattr(oled_care, "_evaluate_script", evaluate)
    shift_thread = threading.Thread(
        target=lambda: shift_result.append(oled_care.shift()))
    shift_thread.start()
    assert entered.wait(2)

    def restore():
        restore_started.set()
        restore_result.append(oled_care.restore())
        restore_done.set()

    restore_thread = threading.Thread(target=restore)
    restore_thread.start()
    assert restore_started.wait(2)
    assert not restore_done.wait(0.05)

    release.set()
    shift_thread.join(2)
    restore_thread.join(2)
    assert not shift_thread.is_alive() and not restore_thread.is_alive()
    assert shift_result == [0] and restore_result == [0]
    assert len(scripts) == 2
    assert not state_file.exists()


def test_operation_lock_failure_never_mutates_and_retains_recovery(
        tmp_path, monkeypatch, capsys):
    state_file = _state_env(tmp_path, monkeypatch)
    assert oled_care.save_state({
        "index": 1, "last_off": 2, "last_h": 2,
        "panels": {"5": {"offset": 0, "height": 32}},
    }) is True
    evaluated: list[str] = []
    real_open = oled_care.os.open

    def fail_lock(path, *args, **kwargs):
        if os.fspath(path) == os.fspath(oled_care._operation_lock_file()):
            raise PermissionError("read-only lock")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(oled_care.os, "open", fail_lock)
    monkeypatch.setattr(
        oled_care, "_evaluate_script", lambda script: evaluated.append(script))

    assert oled_care.shift() == 1
    assert oled_care.restore() == 1
    assert evaluated == []
    assert state_file.is_file()
    assert "operation lock unavailable" in capsys.readouterr().err


def test_quiesce_and_restore_time_out_when_operation_lock_is_busy(
        tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    assert oled_care.save_state({
        "index": 1, "last_off": 2, "last_h": 2,
        "panels": {"5": {"offset": 0, "height": 32}},
    }) is True
    monkeypatch.setattr(oled_care, "_LOCK_WAIT_SECONDS", 0.0)

    with oled_care._operation_lock(1.0) as acquired:
        assert acquired is True
        assert oled_care.quiesce_shifts() is False
        assert oled_care.restore() == 1
    assert state_file.exists()


def test_quiesce_marker_write_failure_is_reported(tmp_path, monkeypatch):
    _state_env(tmp_path, monkeypatch)
    real_open = oled_care.os.open

    def fail_marker(path, *args, **kwargs):
        if os.fspath(path) == os.fspath(oled_care._disabled_file()):
            raise OSError("read-only marker")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(oled_care.os, "open", fail_marker)

    assert oled_care.quiesce_shifts() is False
    assert not oled_care._disabled_file().exists()


def test_shift_never_dispatches_rollback_after_state_save_failure(
        tmp_path, monkeypatch, capsys):
    _state_env(tmp_path, monkeypatch)
    reply = json.dumps({"5": {"offset": 0, "height": 32}})
    scripts: list[str] = []
    monkeypatch.setattr(
        oled_care, "_evaluate_script",
        lambda script: scripts.append(script) or reply,
    )
    monkeypatch.setattr(oled_care, "save_state", lambda _state: False)

    assert oled_care.shift() == 1
    assert len(scripts) == 1
    assert "panel recovery is pending" in capsys.readouterr().err
    assert oled_care._disabled_file().is_file()


def test_shift_without_plasmashell_is_quiet_noop(tmp_path, monkeypatch):
    """Timer fires before login / after logout: no error, no state
    change — the cycle resumes from the same step next fire."""
    state_file = _state_env(tmp_path, monkeypatch)
    monkeypatch.setattr(oled_care, "_evaluate_script", lambda _s: None)

    assert oled_care.shift() == 0
    assert not state_file.exists()


def test_shift_unparseable_reply_is_an_error(tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    monkeypatch.setattr(oled_care, "_evaluate_script",
                        lambda _s: "Error: SyntaxError on line 3\n")

    assert oled_care.shift() == 1
    assert not state_file.exists()


def test_full_cycle_returns_to_start(tmp_path, monkeypatch):
    _state_env(tmp_path, monkeypatch)
    reply = json.dumps({"5": {"offset": 0, "height": 32}})
    monkeypatch.setattr(oled_care, "_evaluate_script", lambda _s: reply)

    offsets, _ = oled_care.build_patterns(oled_care.DEFAULT_MAX_SHIFT_PX)
    for _ in range(len(offsets)):
        assert oled_care.shift() == 0
    state = oled_care.load_state()
    assert state["index"] == 0
    assert state["last_off"] == 0 and state["last_h"] == 0


def test_load_state_rejects_garbage(tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    state_file.parent.mkdir(parents=True)
    state_file.write_text("{not json", encoding="utf-8")
    with pytest.raises(oled_care._StateError, match="could not be read"):
        oled_care.load_state()


@pytest.mark.parametrize("bad_state", [
    {"index": True, "last_off": 0, "last_h": 0, "panels": {}},
    {"index": 0, "last_off": "2", "last_h": 0, "panels": {}},
    {"index": 0, "last_off": 0, "last_h": -1, "panels": {}},
    {"index": 0, "last_off": 0, "last_h": 0,
     "panels": {"5": {"offset": "0", "height": 32}}},
    {"index": 0, "last_off": 0, "last_h": 0,
     "panels": {"5": {"offset": 0, "height": False}}},
])
def test_invalid_existing_state_blocks_shift_and_restore(
        bad_state, tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    state_file.parent.mkdir(parents=True)
    state_file.write_text(json.dumps(bad_state))
    evaluated: list[str] = []
    monkeypatch.setattr(
        oled_care, "_evaluate_script", lambda script: evaluated.append(script))

    assert oled_care.shift() == 1
    assert oled_care.restore() == 1
    assert evaluated == []
    assert state_file.exists()


def test_unreadable_existing_state_blocks_shift_and_restore(
        tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    assert oled_care.save_state({
        "index": 0, "last_off": 0, "last_h": 0,
        "panels": {"5": {"offset": 0, "height": 32}},
    }) is True
    real_read = oled_care.Path.read_text

    def unreadable(path, *args, **kwargs):
        if path == state_file:
            raise PermissionError("unreadable state")
        return real_read(path, *args, **kwargs)

    monkeypatch.setattr(oled_care.Path, "read_text", unreadable)
    monkeypatch.setattr(
        oled_care, "_evaluate_script",
        lambda _script: (_ for _ in ()).throw(
            AssertionError("invalid state must block Plasma mutation")
        ),
    )

    assert oled_care.shift() == 1
    assert oled_care.restore() == 1
    assert state_file.exists()


def test_restore_removes_state(tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    oled_care.save_state({"index": 3, "last_off": 1, "last_h": 2,
                          "panels": {"5": {"offset": 0, "height": 32}}})
    monkeypatch.setattr(oled_care, "_evaluate_script", lambda _s: "restored\n")

    assert oled_care.restore() == 0
    assert not state_file.exists()


def test_restore_without_session_keeps_state(tmp_path, monkeypatch):
    """Can't reach plasmashell → keep the state file so a later restore
    (or the next shift's rebase) can still correct the geometry."""
    state_file = _state_env(tmp_path, monkeypatch)
    oled_care.save_state({"index": 3, "last_off": 1, "last_h": 2,
                          "panels": {"5": {"offset": 0, "height": 32}}})
    monkeypatch.setattr(oled_care, "_evaluate_script", lambda _s: None)

    assert oled_care.restore() == 1
    assert state_file.exists()


def test_restore_keeps_state_without_script_confirmation(
        tmp_path, monkeypatch, capsys):
    state_file = _state_env(tmp_path, monkeypatch)
    oled_care.save_state({"index": 3, "last_off": 1, "last_h": 2,
                          "panels": {"5": {"offset": 0, "height": 32}}})
    monkeypatch.setattr(
        oled_care, "_evaluate_script",
        lambda _s: "Error: evaluateScript failed\n",
    )

    assert oled_care.restore() == 1
    assert state_file.exists()
    assert "did not confirm" in capsys.readouterr().err


def test_restore_reports_state_cleanup_failure(tmp_path, monkeypatch, capsys):
    state_file = _state_env(tmp_path, monkeypatch)
    oled_care.save_state({"index": 3, "last_off": 1, "last_h": 2,
                          "panels": {"5": {"offset": 0, "height": 32}}})
    monkeypatch.setattr(oled_care, "_evaluate_script", lambda _s: "restored\n")
    monkeypatch.setattr(
        oled_care.Path, "unlink",
        lambda _path: (_ for _ in ()).throw(OSError("read-only state")),
    )

    assert oled_care.restore() == 1
    assert state_file.exists()
    assert "state cleanup failed" in capsys.readouterr().err


def test_restore_noop_without_state(tmp_path, monkeypatch):
    _state_env(tmp_path, monkeypatch)

    def _boom(_s):
        raise AssertionError("evaluateScript must not run without state")

    monkeypatch.setattr(oled_care, "_evaluate_script", _boom)
    assert oled_care.restore() == 0


def test_restore_consumes_existing_valid_empty_panel_state(
        tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    assert oled_care.save_state({
        "index": 1, "last_off": 2, "last_h": 2, "panels": {},
    }) is True
    monkeypatch.setattr(
        oled_care,
        "_evaluate_script",
        lambda _script: (_ for _ in ()).throw(
            AssertionError("no geometry should be restored for an empty map")
        ),
    )

    assert oled_care.restore() == 0
    assert not state_file.exists()


def test_restore_retains_corrupt_recovery_state(tmp_path, monkeypatch, capsys):
    state_file = _state_env(tmp_path, monkeypatch)
    state_file.parent.mkdir(parents=True)
    state_file.write_text("{not json\n")

    assert oled_care.restore() == 1
    assert state_file.is_file()
    assert "could not be read" in capsys.readouterr().err


def test_main_rejects_unknown_command(capsys):
    assert oled_care.main([]) == 1
    assert oled_care.main(["dance"]) == 1


def test_main_passes_max_px_to_shift(monkeypatch):
    seen: list[int] = []
    monkeypatch.setattr(oled_care, "shift",
                        lambda max_px: (seen.append(max_px), 0)[1])

    assert oled_care.main(["shift", "--max-px", "3"]) == 0
    assert oled_care.main(["shift", "--max-px=99"]) == 0
    assert oled_care.main(["shift"]) == 0
    assert seen == [3, oled_care.MAX_SHIFT_CEILING_PX,
                    oled_care.DEFAULT_MAX_SHIFT_PX]


# ── shipped systemd units ─────────────────────────────────────────────


def test_offline_units_ship_and_point_at_the_binary(offline):
    service = (offline / "mac-tahoe-liquid-kde-oled.service").read_text()
    timer = (offline / "mac-tahoe-liquid-kde-oled.timer").read_text()
    assert "ExecStart=%h/.local/bin/mac-tahoe-oled-care shift" in service
    assert "Type=oneshot" in service
    assert "OnCalendar=*:0/5" in timer
    assert "Unit=mac-tahoe-liquid-kde-oled.service" in timer
    assert "WantedBy=timers.target" in timer


# ── installer step ────────────────────────────────────────────────────


def _wire_step(tmp_path, monkeypatch):
    from steps import oled_care as step

    # These tests assert the systemd artefacts (.service/.timer) + enable
    # calls. Pin the init to systemd so they exercise that path regardless of
    # the CI host, which resolves to OpenRC (no /run/systemd/system) and would
    # otherwise take the crontab branch. The OpenRC branch has its own tests.
    monkeypatch.setenv("MTTKDE_INIT", "systemd")

    home = tmp_path / "home"
    bin_dest = home / ".local/bin/mac-tahoe-oled-care"
    svc_dir = home / ".config/systemd/user"
    state = home / ".local/state/mac-tahoe-liquid-kde/oled-care.json"
    calls: list[list[str]] = []

    monkeypatch.setattr(step, "BIN_DEST", bin_dest)
    monkeypatch.setattr(step, "SVC_DIR", svc_dir)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_STATE_HOME", str(state.parents[1]))
    monkeypatch.setattr(oled_care, "_PROC_ROOT", tmp_path / "no-proc")
    monkeypatch.setattr(step, "run_user",
                        lambda cmd, **_kw: (
                            calls.append(list(cmd))
                            or subprocess.CompletedProcess(cmd, 0)
                        ))
    # Never inspect or rewrite the developer/CI account's real crontab.
    monkeypatch.setattr(
        step, "remove_periodic",
        lambda _tag: step.RemovalStatus.UNAVAILABLE,
    )
    # Legacy process-drain tests provide an isolated fake /proc explicitly.
    monkeypatch.setattr(
        step, "_wait_for_legacy_shifts", lambda: (True, False),
    )
    monkeypatch.setattr(
        step, "_prepare_recovery_state", lambda **_kwargs: True,
    )
    for fn in ("ok", "info", "warn"):
        monkeypatch.setattr(step, fn, lambda _msg: None)
    return step, home, calls


def test_step_install_enabled_copies_and_enables(tmp_path, monkeypatch):
    step, home, calls = _wire_step(tmp_path, monkeypatch)
    monkeypatch.setenv("FEAT_OLED_CARE", "true")
    monkeypatch.delenv("OLED_INTERVAL", raising=False)
    monkeypatch.delenv("OLED_MAX_SHIFT", raising=False)

    step.install()

    assert step.BIN_DEST.is_file()
    assert step.BIN_DEST.read_bytes() == step.PY_SRC.read_bytes()
    assert list(step.BIN_DEST.parent.glob(f".{step.BIN_DEST.name}.*.tmp")) == []
    assert not oled_care._disabled_file().exists()
    assert step.BIN_DEST.stat().st_mode & 0o111
    for unit in step.UNITS:
        assert (step.SVC_DIR / unit).is_file()
    timer = (step.SVC_DIR / "mac-tahoe-liquid-kde-oled.timer").read_text()
    service = (step.SVC_DIR / "mac-tahoe-liquid-kde-oled.service").read_text()
    assert "OnCalendar=*:0/5" in timer
    assert "mac-tahoe-oled-care shift --max-px 8" in service
    flat = [" ".join(c) for c in calls]
    assert any("enable" in c for c in flat)
    assert any("restart" in c and "timer" in c for c in flat)


def test_step_install_stamps_custom_interval_and_amplitude(tmp_path, monkeypatch):
    """--oled-interval / --oled-max-shift land in the written units."""
    step, home, calls = _wire_step(tmp_path, monkeypatch)
    monkeypatch.setenv("FEAT_OLED_CARE", "true")
    monkeypatch.setenv("OLED_INTERVAL", "3")
    monkeypatch.setenv("OLED_MAX_SHIFT", "4")

    step.install()

    timer = (step.SVC_DIR / "mac-tahoe-liquid-kde-oled.timer").read_text()
    service = (step.SVC_DIR / "mac-tahoe-liquid-kde-oled.service").read_text()
    assert "OnCalendar=*:0/3" in timer
    assert "mac-tahoe-oled-care shift --max-px 4" in service


def test_step_install_clamps_garbage_settings(tmp_path, monkeypatch):
    step, home, calls = _wire_step(tmp_path, monkeypatch)
    monkeypatch.setenv("FEAT_OLED_CARE", "true")
    monkeypatch.setenv("OLED_INTERVAL", "banana")
    monkeypatch.setenv("OLED_MAX_SHIFT", "999")

    step.install()

    timer = (step.SVC_DIR / "mac-tahoe-liquid-kde-oled.timer").read_text()
    service = (step.SVC_DIR / "mac-tahoe-liquid-kde-oled.service").read_text()
    assert "OnCalendar=*:0/5" in timer
    assert f"--max-px {oled_care.MAX_SHIFT_CEILING_PX}" in service


def test_step_install_disabled_tears_down_leftovers(tmp_path, monkeypatch):
    """Plain re-install without the flag must remove what a previous
    flagged install left behind — no orphaned timer keeps shifting."""
    step, home, calls = _wire_step(tmp_path, monkeypatch)
    monkeypatch.setenv("FEAT_OLED_CARE", "false")
    monkeypatch.setattr(step, "_restore_panels",
                        lambda: calls.append(["RESTORE"]) or True)
    step.BIN_DEST.parent.mkdir(parents=True)
    step.BIN_DEST.write_text("#!stub")
    step.SVC_DIR.mkdir(parents=True)
    for unit in step.UNITS:
        (step.SVC_DIR / unit).write_text("[Unit]")

    step.install()

    assert not step.BIN_DEST.exists()
    assert not any((step.SVC_DIR / u).exists() for u in step.UNITS)
    flat = [" ".join(c) for c in calls]
    assert any("disable" in c for c in flat)
    # timer must be stopped BEFORE geometry is restored — a fire landing
    # in between would re-shift the panels we just put back
    assert flat.index("RESTORE") > max(
        i for i, c in enumerate(flat) if "disable" in c)
    disable_calls = [c for c in flat if "disable --now" in c]
    assert "oled.timer" in disable_calls[0]
    assert "oled.service" in disable_calls[1]
    assert oled_care._disabled_file().is_file()


def test_step_install_default_is_off(tmp_path, monkeypatch):
    step, home, calls = _wire_step(tmp_path, monkeypatch)
    monkeypatch.delenv("FEAT_OLED_CARE", raising=False)

    step.install()

    assert not step.BIN_DEST.exists()


def test_step_uninstall_removes_everything(tmp_path, monkeypatch):
    step, home, calls = _wire_step(tmp_path, monkeypatch)
    step.BIN_DEST.parent.mkdir(parents=True)
    step.BIN_DEST.write_text("#!stub")
    step.SVC_DIR.mkdir(parents=True)
    for unit in step.UNITS:
        (step.SVC_DIR / unit).write_text("[Unit]")

    step.uninstall()

    assert not step.BIN_DEST.exists()
    assert not any((step.SVC_DIR / u).exists() for u in step.UNITS)
    assert any("disable" in " ".join(c) for c in calls)


def test_step_uninstall_retains_recovery_when_panels_cannot_restore(
        tmp_path, monkeypatch):
    step, _home, calls = _wire_step(tmp_path, monkeypatch)
    step.BIN_DEST.parent.mkdir(parents=True)
    step.BIN_DEST.write_text("#!stub")
    state_file = step._state_file()
    state_file.parent.mkdir(parents=True)
    state_file.write_text("{}\n")
    step.SVC_DIR.mkdir(parents=True)
    for unit in step.UNITS:
        (step.SVC_DIR / unit).write_text("[Unit]")
    monkeypatch.setattr(step, "_restore_panels", lambda: False)
    failures: list[str] = []
    monkeypatch.setattr(step, "fail", failures.append)

    step.uninstall()

    # The schedule is gone and the replacement obeys the tombstone, so keep
    # the recovery command available until geometry can actually be restored.
    assert step.BIN_DEST.is_file()
    assert step.BIN_DEST.read_bytes() == step.PY_SRC.read_bytes()
    assert state_file.is_file()
    assert not any((step.SVC_DIR / unit).exists() for unit in step.UNITS)
    assert any("disable" in " ".join(call) for call in calls)
    assert any("removal incomplete" in message for message in failures)


def test_step_uninstall_retains_helper_and_state_when_cron_removal_fails(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    monkeypatch.setenv("MTTKDE_INIT", "openrc")
    step.BIN_DEST.parent.mkdir(parents=True)
    step.BIN_DEST.write_text("#!stub")
    restored: list[bool] = []
    failures: list[str] = []
    monkeypatch.setattr(
        step, "remove_periodic",
        lambda _tag: step.RemovalStatus.ERROR,
    )
    monkeypatch.setattr(
        step, "_restore_panels", lambda: restored.append(True) or True,
    )
    monkeypatch.setattr(step, "fail", failures.append)

    step.uninstall()

    # The replacement understands the tombstone and is retained for recovery;
    # an uncertain trigger teardown must never proceed into restore.
    assert step.BIN_DEST.exists()
    assert restored == []
    assert any("removal incomplete" in message for message in failures)


def test_step_does_not_restore_if_schedule_and_helper_cannot_be_stopped(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    monkeypatch.setattr(
        step, "_retire_runtime", lambda **_kwargs: (False, False))
    monkeypatch.setattr(
        step, "_restore_panels",
        lambda: (_ for _ in ()).throw(
            AssertionError("unsafe restore must not start")
        ),
    )
    failures: list[str] = []
    monkeypatch.setattr(step, "fail", failures.append)

    step.uninstall()

    assert any("could not be retired safely" in message
               for message in failures)


def test_step_does_not_restore_when_runtime_cannot_be_quiesced(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    monkeypatch.setattr(step, "_quiesce_shifts", lambda: False)
    monkeypatch.setattr(
        step, "_restore_panels",
        lambda: (_ for _ in ()).throw(
            AssertionError("uncoordinated restore must not start")
        ),
    )
    failures: list[str] = []
    monkeypatch.setattr(step, "fail", failures.append)

    step.uninstall()

    assert any("could not be retired safely" in message for message in failures)


def test_step_clears_tombstone_only_after_scheduler_success(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    monkeypatch.setenv("FEAT_OLED_CARE", "true")
    events: list[str] = []
    monkeypatch.setattr(
        step, "_retire_runtime",
        lambda **_kwargs: (events.append("retire") or False, True),
    )
    monkeypatch.setattr(
        step, "_schedule_systemd",
        lambda _interval, _max_px: events.append("schedule") or True,
    )
    monkeypatch.setattr(
        step, "_enable_shifts", lambda: events.append("enable") or True)

    step.install()

    assert events == ["retire", "schedule", "enable"]


def test_step_never_reschedules_over_uncertain_transition(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    monkeypatch.setenv("FEAT_OLED_CARE", "true")
    with oled_care._operation_lock(1.0) as acquired:
        assert acquired
        oled_care._disable_unlocked(oled_care._MARKER_TRANSITION)
    scheduled: list[bool] = []
    failures: list[str] = []
    monkeypatch.setattr(
        step, "_schedule_systemd",
        lambda *_args: scheduled.append(True) or True,
    )
    monkeypatch.setattr(step, "fail", failures.append)

    step.install()

    assert scheduled == []
    assert oled_care._marker_state_unlocked() == oled_care._MARKER_TRANSITION
    assert step.BIN_DEST.is_file()
    assert any("runtime could not be retired" in item for item in failures)


def test_runtime_retirement_drains_between_triggers_and_service(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    events: list[str] = []
    monkeypatch.setattr(
        step, "_quiesce_shifts", lambda: events.append("quiesce") or True)
    monkeypatch.setattr(
        step, "_replace_current_helper",
        lambda **_kwargs: events.append("replace") or True)
    monkeypatch.setattr(
        step, "_teardown_triggers",
        lambda: (events.append("triggers") or True, True))
    monkeypatch.setattr(
        step, "_wait_for_legacy_shifts",
        lambda: (events.append("drain") or True, False))
    monkeypatch.setattr(
        step, "_teardown_service",
        lambda: (events.append("service") or True, True))

    removed, safe = step._retire_runtime(require_helper=True)

    assert removed is True and safe is True
    assert events == ["quiesce", "replace", "triggers", "drain", "service"]


def test_removed_legacy_trigger_requires_known_recovery_location(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    required: list[bool] = []
    monkeypatch.setattr(step, "_canonical_storage_initialized", lambda: False)
    monkeypatch.setattr(step, "_quiesce_shifts", lambda: True)
    monkeypatch.setattr(step, "_replace_current_helper", lambda **_kw: True)
    monkeypatch.setattr(step, "_teardown_triggers", lambda: (True, True))
    monkeypatch.setattr(step, "_wait_for_legacy_shifts", lambda: (True, False))
    monkeypatch.setattr(
        step, "_prepare_recovery_state",
        lambda *, require_known_legacy: required.append(
            require_known_legacy) or True,
    )
    monkeypatch.setattr(step, "_teardown_service", lambda: (False, True))
    monkeypatch.setattr(step, "_recovery_uncertain", lambda: False)

    _removed, safe = step._retire_runtime(require_helper=False)

    assert safe is True
    assert required == [True]


def test_runtime_retirement_timeout_never_stops_service(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    monkeypatch.setattr(step, "_quiesce_shifts", lambda: True)
    monkeypatch.setattr(step, "_replace_current_helper", lambda **_kw: True)
    monkeypatch.setattr(step, "_teardown_triggers", lambda: (True, True))
    monkeypatch.setattr(
        step, "_wait_for_legacy_shifts", lambda: (False, True),
    )
    monkeypatch.setattr(
        step, "_teardown_service",
        lambda: (_ for _ in ()).throw(
            AssertionError("service must not be killed before legacy drain")
        ),
    )

    assert step._retire_runtime(require_helper=False) == (True, False)


def test_observed_legacy_shift_without_state_commit_marks_recovery_uncertain(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    step.BIN_DEST.parent.mkdir(parents=True)
    step.BIN_DEST.write_text("#!/usr/bin/env python3\n# older helper\n")
    marked: list[bool] = []
    monkeypatch.setattr(step, "_quiesce_shifts", lambda: True)
    monkeypatch.setattr(step, "_replace_current_helper", lambda **_kw: True)
    monkeypatch.setattr(step, "_teardown_triggers", lambda: (True, True))
    monkeypatch.setattr(
        step, "_wait_for_legacy_shifts", lambda: (True, True),
    )
    monkeypatch.setattr(step, "_prepare_recovery_state", lambda **_kw: True)
    monkeypatch.setattr(step, "_recovery_signature", lambda: (b"same",))
    monkeypatch.setattr(
        step, "_mark_recovery_uncertain",
        lambda: marked.append(True) or True,
    )
    monkeypatch.setattr(step, "_teardown_service", lambda: (True, True))
    monkeypatch.setattr(step, "_recovery_uncertain", lambda: False)

    removed, safe = step._retire_runtime(require_helper=True)

    assert removed is True and safe is False
    assert marked == [True]


def test_legacy_scan_matches_only_exact_same_user_shift_argv(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    proc = tmp_path / "proc"
    proc.mkdir()
    commands = {
        "9876541": ["python3", str(step.BIN_DEST), "shift", "--max-px", "8"],
        "9876542": ["python3", str(step.BIN_DEST), "status"],
        "9876543": ["python3", str(step.BIN_DEST) + "-other", "shift"],
    }
    for pid, argv in commands.items():
        process = proc / pid
        process.mkdir()
        (process / "cmdline").write_bytes(
            b"\0".join(os.fsencode(arg) for arg in argv) + b"\0")
    monkeypatch.setenv("SUDO_UID", str(os.getuid()))
    monkeypatch.setattr(step, "_PROC_ROOT", proc)

    assert step._running_legacy_shift_pids() == {9876541}


def test_step_scheduler_failure_keeps_tombstone_and_removes_helper(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    monkeypatch.setenv("FEAT_OLED_CARE", "true")
    monkeypatch.setattr(step, "_schedule_systemd", lambda *_args: False)
    enabled: list[bool] = []
    monkeypatch.setattr(
        step, "_enable_shifts", lambda: enabled.append(True) or True)
    failures: list[str] = []
    monkeypatch.setattr(step, "fail", failures.append)

    step.install()

    assert enabled == []
    assert not step.BIN_DEST.exists()
    assert oled_care._disabled_file().is_file()
    assert any("scheduler could not be enabled" in message
               for message in failures)


def test_systemd_stop_failure_marks_oled_teardown_incomplete(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    step.SVC_DIR.mkdir(parents=True)
    (step.SVC_DIR / step.UNITS[0]).write_text("[Unit]\n")
    monkeypatch.setattr(
        step, "_user_service",
        lambda *args: args == ("daemon-reload",),
    )
    monkeypatch.setattr(
        step, "remove_periodic",
        lambda _tag: step.RemovalStatus.UNAVAILABLE,
    )

    removed, complete = step._teardown_units()

    assert removed is True
    assert complete is False


def test_systemd_teardown_rejects_loaded_active_unit_without_file(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    probes: list[str] = []
    monkeypatch.setattr(step, "_user_service", lambda *_args: False)
    monkeypatch.setattr(
        step, "_systemd_unit_neutralized",
        lambda unit: probes.append(unit) or False,
    )

    removed, complete = step._teardown_units()

    assert removed is False
    assert complete is False
    assert probes == [step.TIMER_UNIT, step.SERVICE_UNIT]


def test_systemd_failed_stop_proof_requires_inactive_and_disabled(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    monkeypatch.setattr(
        step, "user_service_manager_command",
        lambda *args: ["systemctl", "--user", *args],
    )

    def probe(active, enabled):
        results = iter((
            subprocess.CompletedProcess([], 3, stdout=active, stderr=""),
            subprocess.CompletedProcess([], 1, stdout=enabled, stderr=""),
        ))
        monkeypatch.setattr(
            step, "run_user", lambda *_args, **_kwargs: next(results))
        return step._systemd_unit_neutralized("oled.service")

    assert probe("inactive\n", "disabled\n") is True
    assert probe("active\n", "disabled\n") is False
    assert probe("inactive\n", "enabled\n") is False


def test_systemd_teardown_accepts_explicit_inactive_units_without_files(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    probes: list[str] = []
    monkeypatch.setattr(
        step, "_user_service",
        lambda *args: args == ("daemon-reload",),
    )
    monkeypatch.setattr(
        step, "_systemd_unit_neutralized",
        lambda unit: probes.append(unit) or True,
    )

    removed, complete = step._teardown_units()

    assert removed is False
    assert complete is True
    assert probes == [step.TIMER_UNIT, step.SERVICE_UNIT]


def test_step_restore_panels_propagates_unreachable_session(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    state_file = step._state_file()
    state_file.parent.mkdir(parents=True)
    state_file.write_text("{}\n")
    monkeypatch.setattr(oled_care, "restore", lambda: 1)

    assert step._restore_panels() is False
    assert state_file.is_file()


def test_step_restore_checks_under_runtime_lock_when_state_looks_absent(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    called: list[bool] = []
    monkeypatch.setattr(
        oled_care, "restore", lambda: called.append(True) or 0,
    )

    assert not step._state_file().exists()
    assert step._restore_panels() is True
    assert called == [True]


def test_step_restore_uses_canonical_state_home(tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    custom = tmp_path / "custom-state"
    monkeypatch.setenv("XDG_STATE_HOME", str(custom))
    state_file = step._state_file()
    assert custom not in state_file.parents
    state_file.parent.mkdir(parents=True)
    state_file.write_text("{}\n")
    called: list[bool] = []

    def restore_custom():
        called.append(True)
        state_file.unlink()
        return 0

    monkeypatch.setattr(oled_care, "restore", restore_custom)

    assert step._restore_panels() is True
    assert called == [True]
    assert not state_file.exists()


# ── CLI flag registration ─────────────────────────────────────────────


def test_cli_registers_oled_care_defaulting_off():
    import cli

    assert "oled_care" in cli.ALL_FEATURES
    assert cli.DEFAULT_FEATURES["oled_care"] is False
    assert "oled_care" in cli.FEATURE_DESC
    assert "--oled-care" in cli.INSTALL_HELP


def test_cli_parses_oled_care_flags():
    import cli

    assert cli.parse_args(["--oled-care"]).cli_overrides == {"oled_care": True}
    assert cli.parse_args(["--no-oled-care"]).cli_overrides == {"oled_care": False}


def test_cli_parses_interval_and_max_shift_both_forms():
    import cli

    p = cli.parse_args(["--oled-interval=3", "--oled-max-shift", "4"])
    assert p.oled_interval == 3
    assert p.oled_max_shift == 4
    # clamped, and garbage falls back to the default
    assert cli.parse_args(["--oled-interval=0"]).oled_interval == 1
    assert cli.parse_args(["--oled-interval=120"]).oled_interval == 59
    assert cli.parse_args(["--oled-max-shift=99"]).oled_max_shift == 16
    assert cli.parse_args(["--oled-interval=banana"]).oled_interval == 5
    # untouched when not passed
    assert cli.parse_args([]).oled_interval is None


def test_cli_settings_survive_save_load_roundtrip(tmp_path, monkeypatch):
    import cli

    monkeypatch.setattr(cli, "CONFIG_FILE", tmp_path / "features.json")
    feat = dict(cli.DEFAULT_FEATURES)
    feat["oled_care"] = True
    feat["oled_interval"] = 7
    feat["oled_max_shift"] = 3
    cli.save_features(feat)

    loaded = cli.load_features()
    assert loaded["oled_care"] is True
    assert loaded["oled_interval"] == 7
    assert loaded["oled_max_shift"] == 3


def test_cli_export_env_publishes_oled_settings(monkeypatch):
    import cli

    # export_env writes THEME_MODE + every FEAT_* — sandbox the env so
    # the values can't leak into later tests.
    monkeypatch.setattr(os, "environ", dict(os.environ))
    cli.export_env({"oled_care": True, "oled_interval": 9,
                    "oled_max_shift": "banana"})
    assert os.environ["FEAT_OLED_CARE"] == "true"
    assert os.environ["OLED_INTERVAL"] == "9"
    assert os.environ["OLED_MAX_SHIFT"] == "8"
    assert os.environ["MTTKDE_EXISTING_INSTALL"] == "false"
    assert os.environ["MTTKDE_RESET_WALLPAPERS"] == "false"


def test_cli_export_env_publishes_one_shot_update_actions(monkeypatch):
    import cli

    monkeypatch.setattr(os, "environ", dict(os.environ))
    cli.export_env({"_existing_install": True,
                    "_reset_wallpapers": True})
    assert os.environ["MTTKDE_EXISTING_INSTALL"] == "true"
    assert os.environ["MTTKDE_RESET_WALLPAPERS"] == "true"
