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

import oled_care


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
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return tmp_path / "state" / "mac-tahoe-liquid-kde" / "oled-care.json"


def test_shift_persists_plasmashell_reply(tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    reply = json.dumps({"5": {"offset": 0, "height": 32}})
    monkeypatch.setattr(oled_care, "_evaluate_script", lambda _s: reply + "\n")

    assert oled_care.shift() == 0
    state = json.loads(state_file.read_text())
    assert state["index"] == 1
    assert state["last_off"] == 2 and state["last_h"] == 2
    assert state["panels"] == {"5": {"offset": 0, "height": 32}}


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


def test_shift_reports_failure_when_state_cannot_be_saved(tmp_path, monkeypatch):
    _state_env(tmp_path, monkeypatch)
    reply = json.dumps({"5": {"offset": 0, "height": 32}})
    scripts: list[str] = []

    def evaluate(script):
        scripts.append(script)
        return reply if len(scripts) == 1 else "restored\n"

    monkeypatch.setattr(oled_care, "_evaluate_script", evaluate)
    monkeypatch.setattr(oled_care, "save_state", lambda _state: False)

    assert oled_care.shift() == 1
    assert len(scripts) == 2
    assert 'var lastOff = 2;' in scripts[1]
    assert 'var lastH = 2;' in scripts[1]


def test_shift_reports_failed_rollback_after_state_save_failure(
        tmp_path, monkeypatch, capsys):
    _state_env(tmp_path, monkeypatch)
    reply = json.dumps({"5": {"offset": 0, "height": 32}})
    responses = iter((reply, None))
    monkeypatch.setattr(oled_care, "_evaluate_script", lambda _s: next(responses))
    monkeypatch.setattr(oled_care, "save_state", lambda _state: False)

    assert oled_care.shift() == 1
    assert "could not be rolled back" in capsys.readouterr().err


def test_shift_rejects_rollback_without_script_confirmation(
        tmp_path, monkeypatch, capsys):
    _state_env(tmp_path, monkeypatch)
    reply = json.dumps({"5": {"offset": 0, "height": 32}})
    responses = iter((reply, "Error: evaluateScript failed\n"))
    monkeypatch.setattr(oled_care, "_evaluate_script", lambda _s: next(responses))
    monkeypatch.setattr(oled_care, "save_state", lambda _state: False)

    assert oled_care.shift() == 1
    assert "could not be rolled back" in capsys.readouterr().err


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


def test_load_state_survives_garbage(tmp_path, monkeypatch):
    state_file = _state_env(tmp_path, monkeypatch)
    state_file.parent.mkdir(parents=True)
    state_file.write_text("{not json", encoding="utf-8")
    assert oled_care.load_state() == {
        "index": 0, "last_off": 0, "last_h": 0, "panels": {}}


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
    monkeypatch.setenv("XDG_STATE_HOME", str(state.parents[1]))
    monkeypatch.setattr(step, "run_user",
                        lambda cmd, **_kw: (
                            calls.append(list(cmd))
                            or subprocess.CompletedProcess(cmd, 0)
                        ))
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

    # Even though geometry recovery remains pending, removing the command
    # target guarantees a scheduler teardown error cannot shift it again.
    assert not step.BIN_DEST.exists()
    assert state_file.is_file()
    assert not any((step.SVC_DIR / unit).exists() for unit in step.UNITS)
    assert any("disable" in " ".join(call) for call in calls)
    assert any("removal incomplete" in message for message in failures)


def test_step_uninstall_neutralizes_helper_when_cron_removal_fails(
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

    assert not step.BIN_DEST.exists()
    assert restored == [True]
    assert any("removal incomplete" in message for message in failures)


def test_step_does_not_restore_if_schedule_and_helper_cannot_be_stopped(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    monkeypatch.setattr(step, "_teardown_units", lambda: (False, False))
    monkeypatch.setattr(step, "_remove_helper", lambda: (False, False))
    monkeypatch.setattr(
        step, "_restore_panels",
        lambda: (_ for _ in ()).throw(
            AssertionError("unsafe restore must not start")
        ),
    )
    failures: list[str] = []
    monkeypatch.setattr(step, "fail", failures.append)

    step.uninstall()

    assert any("scheduling could not be neutralized" in message
               for message in failures)


def test_systemd_stop_failure_marks_oled_teardown_incomplete(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    step.SVC_DIR.mkdir(parents=True)
    (step.SVC_DIR / step.UNITS[0]).write_text("[Unit]\n")
    monkeypatch.setattr(step, "_user_service", lambda *_args: False)
    monkeypatch.setattr(
        step, "remove_periodic",
        lambda _tag: step.RemovalStatus.UNAVAILABLE,
    )

    removed, complete = step._teardown_units()

    assert removed is True
    assert complete is False


def test_step_restore_panels_propagates_unreachable_session(
        tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    state_file = step._state_file()
    state_file.parent.mkdir(parents=True)
    state_file.write_text("{}\n")
    monkeypatch.setattr(oled_care, "restore", lambda: 1)

    assert step._restore_panels() is False
    assert state_file.is_file()


def test_step_restore_uses_custom_xdg_state_home(tmp_path, monkeypatch):
    step, _home, _calls = _wire_step(tmp_path, monkeypatch)
    custom = tmp_path / "custom-state"
    monkeypatch.setenv("XDG_STATE_HOME", str(custom))
    state_file = custom / "mac-tahoe-liquid-kde/oled-care.json"
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
