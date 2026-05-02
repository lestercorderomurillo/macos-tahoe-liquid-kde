# USELESS: monkeypatches _require_root_and_drop_to_user — verifies the gate exists, not that the install is usable
"""Tests for the install/uninstall CLI: argument parsing, root
precondition, GitHub version checker."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def cli_module():
    import cli
    return cli


# ── --check-update flag parsing ─────────────────────────────────────────
def test_parse_args_recognizes_check_update(cli_module):
    parsed = cli_module.parse_args(["--check-update"])
    assert parsed.check_update is True


def test_parse_args_default_check_update_false(cli_module):
    parsed = cli_module.parse_args([])
    assert parsed.check_update is False


def test_install_order_puts_core_theme_steps_before_optional_integrations(cli_module):
    order = cli_module.INSTALL_ORDER
    assert order.index("global_theme") < order.index("plasmoids")
    assert order.index("wallpapers") < order.index("plasmoids")
    assert order.index("color_schemes") < order.index("wallpapers")
    assert order.index("plasma_theme") < order.index("nautilus")
    assert order.index("global_theme") < order.index("portals")
    assert order.index("nautilus") < order.index("portals")


def test_layout_is_installed_uses_step_probe(cli_module):
    class FakeMod:
        @staticmethod
        def is_installed():
            return True

    cli_module.step_module = lambda _name: FakeMod
    assert cli_module._layout_is_installed() is True


# ── parse_semver ────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,expected", [
    ("0.8.0",          (0, 8, 0)),
    ("1.2.3",          (1, 2, 3)),
    ("v0.8.0",         (0, 8, 0)),
    ("V1.0.0",         (1, 0, 0)),
    ("1.2",            (1, 2, 0)),
    ("3",              (3, 0, 0)),
    ("1.0.0-rc1",      (1, 0, 0)),
    ("2.5.1+meta.42",  (2, 5, 1)),
    ("",               (0, 0, 0)),
    ("garbage",        (0, 0, 0)),
    ("1.2.notnumeric", (1, 2, 0)),
])
def test_parse_semver(cli_module, raw, expected):
    assert cli_module.parse_semver(raw) == expected


def test_parse_semver_orders_correctly(cli_module):
    """Reading a 'newer' tag from GitHub means tuple-comparing — make sure
    the natural ordering matches our intent across mixed v-prefix styles."""
    assert cli_module.parse_semver("v0.8.0") > cli_module.parse_semver("0.7.14")
    assert cli_module.parse_semver("0.7.14") > cli_module.parse_semver("0.7.9")
    assert cli_module.parse_semver("1.0.0") > cli_module.parse_semver("0.99.99")


# ── fetch_latest_release ────────────────────────────────────────────────
def test_fetch_latest_release_returns_none_when_env_disables(monkeypatch, cli_module):
    monkeypatch.setenv("MAC_TAHOE_NO_UPDATE_CHECK", "true")
    # urlopen must NOT be called when the env var is set — even mocking it
    # to raise would pass an over-permissive test, so we mock it to a hard
    # failure and rely on the env-var short-circuit firing first.
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *_a, **_k: pytest.fail("should not fetch"))
    assert cli_module.fetch_latest_release() is None


def test_fetch_latest_release_returns_none_on_network_error(monkeypatch, cli_module):
    monkeypatch.delenv("MAC_TAHOE_NO_UPDATE_CHECK", raising=False)
    import urllib.request

    def raise_urlerror(*_a, **_k):
        raise OSError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", raise_urlerror)
    assert cli_module.fetch_latest_release() is None


def test_fetch_latest_release_strips_v_prefix(monkeypatch, cli_module):
    monkeypatch.delenv("MAC_TAHOE_NO_UPDATE_CHECK", raising=False)
    import urllib.request

    payload = json.dumps({"tag_name": "v1.2.3"}).encode()

    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return payload

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *_a, **_k: FakeResp())
    assert cli_module.fetch_latest_release() == "1.2.3"


def test_fetch_latest_release_handles_missing_tag(monkeypatch, cli_module):
    monkeypatch.delenv("MAC_TAHOE_NO_UPDATE_CHECK", raising=False)
    import urllib.request

    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"message": "Not Found"}'

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *_a, **_k: FakeResp())
    assert cli_module.fetch_latest_release() is None


# ── check_for_updates banner behaviour ───────────────────────────────────
def test_check_for_updates_prints_banner_when_newer(monkeypatch, capsys, cli_module):
    monkeypatch.setattr(cli_module, "read_version", lambda: "0.7.14")
    monkeypatch.setattr(cli_module, "fetch_latest_release", lambda **_: "0.8.0")
    assert cli_module.check_for_updates() is True
    out = capsys.readouterr().out
    assert "Update available" in out
    assert "0.7.14" in out and "0.8.0" in out
    # Plain users should be told *why* updating matters — that's the whole
    # point of having a checker for a public theme repo.
    assert "style breakage" in out or "fix" in out.lower()


def test_check_for_updates_silent_when_up_to_date(monkeypatch, capsys, cli_module):
    monkeypatch.setattr(cli_module, "read_version", lambda: "0.8.0")
    monkeypatch.setattr(cli_module, "fetch_latest_release", lambda **_: "0.8.0")
    assert cli_module.check_for_updates() is False
    assert capsys.readouterr().out == ""


def test_check_for_updates_silent_when_offline(monkeypatch, capsys, cli_module):
    monkeypatch.setattr(cli_module, "read_version", lambda: "0.8.0")
    monkeypatch.setattr(cli_module, "fetch_latest_release", lambda **_: None)
    assert cli_module.check_for_updates() is False
    assert capsys.readouterr().out == ""


def test_check_for_updates_verbose_announces_up_to_date(monkeypatch, capsys, cli_module):
    monkeypatch.setattr(cli_module, "read_version", lambda: "0.8.0")
    monkeypatch.setattr(cli_module, "fetch_latest_release", lambda **_: "0.8.0")
    cli_module.check_for_updates(verbose=True)
    out = capsys.readouterr().out
    assert "0.8.0" in out


def test_check_for_updates_does_not_downgrade(monkeypatch, capsys, cli_module):
    """If we are AHEAD of the latest tag (developing toward a new release),
    don't nag with an upgrade banner — that would confuse contributors."""
    monkeypatch.setattr(cli_module, "read_version", lambda: "0.9.0")
    monkeypatch.setattr(cli_module, "fetch_latest_release", lambda **_: "0.8.0")
    assert cli_module.check_for_updates() is False
    assert capsys.readouterr().out == ""


def test_check_for_updates_inline_overwrites_checking_line(
        monkeypatch, capsys, cli_module):
    """``inline=True`` is what runs in the install flow — show the user
    that we *are* checking, then replace the line with the verdict so
    the rest of the install output starts on a clean line."""
    monkeypatch.setattr(cli_module, "read_version", lambda: "0.8.0")
    monkeypatch.setattr(cli_module, "fetch_latest_release", lambda **_: "0.8.0")
    monkeypatch.setattr(cli_module.time, "sleep", lambda _: None)

    cli_module.check_for_updates(inline=True)
    out = capsys.readouterr().out
    assert "Checking for updates" in out
    # Cursor reset + clear-line escape must come BEFORE the verdict so
    # the transient "Checking…" line does not stay on screen.
    checking_pos = out.index("Checking")
    clear_pos = out.find(cli_module._CLEAR_LINE)
    verdict_pos = out.find("On the latest version")
    assert clear_pos != -1
    assert checking_pos < clear_pos < verdict_pos


def test_check_for_updates_inline_announces_when_offline(
        monkeypatch, capsys, cli_module):
    monkeypatch.setattr(cli_module, "read_version", lambda: "0.8.0")
    monkeypatch.setattr(cli_module, "fetch_latest_release", lambda **_: None)
    monkeypatch.setattr(cli_module.time, "sleep", lambda _: None)

    cli_module.check_for_updates(inline=True)
    out = capsys.readouterr().out
    assert "Checking for updates" in out
    assert "Could not reach GitHub" in out


@pytest.mark.parametrize("latest,verdict_substr", [
    ("0.8.0", "On the latest version"),
    ("0.9.0", "Update available"),
    (None,    "Could not reach GitHub"),
])
def test_check_for_updates_inline_pauses_for_user_to_read(
        monkeypatch, cli_module, latest, verdict_substr):
    """The pause is the whole point of ``inline=True``: without it the
    verdict scrolls off-screen the moment the next install step prints
    its banner."""
    monkeypatch.setattr(cli_module, "read_version", lambda: "0.8.0")
    monkeypatch.setattr(cli_module, "fetch_latest_release", lambda **_: latest)
    sleeps: list[float] = []
    monkeypatch.setattr(cli_module.time, "sleep", sleeps.append)

    cli_module.check_for_updates(inline=True)
    assert sleeps, f"expected a pause after showing {verdict_substr!r}"
    # Anything under a second is too short to read; we set 2s.
    assert sleeps[0] >= 1.5


def test_check_for_updates_inline_no_double_blank_line_before_verdict(
        monkeypatch, capsys, cli_module):
    """``confirm()`` already trails with a blank line. If
    ``check_for_updates(inline=True)`` *also* prints one before the
    transient 'Checking…' line, the user sees an awkward gap between
    the [Y/n] prompt and the verdict. Output must start directly with
    the Checking… line."""
    monkeypatch.setattr(cli_module, "read_version", lambda: "0.8.0")
    monkeypatch.setattr(cli_module, "fetch_latest_release", lambda **_: "0.8.0")
    monkeypatch.setattr(cli_module.time, "sleep", lambda _: None)

    cli_module.check_for_updates(inline=True)
    out = capsys.readouterr().out
    assert not out.startswith("\n"), (
        "inline check_for_updates leaked a leading blank line — confirm() "
        "already prints one and we're now stacking two."
    )


def test_check_for_updates_verdict_indent_matches_ok_calls(
        monkeypatch, capsys, cli_module):
    """The 'On the latest version' line lives in the same vertical column
    as ``ok()`` output (``  ✓  msg``). If we drift by an extra two
    spaces, the verdict no longer aligns with the install steps that
    follow it and looks visually broken on the user's terminal."""
    monkeypatch.setattr(cli_module, "read_version", lambda: "0.8.0")
    monkeypatch.setattr(cli_module, "fetch_latest_release", lambda **_: "0.8.0")
    monkeypatch.setattr(cli_module.time, "sleep", lambda _: None)

    cli_module.check_for_updates(inline=True)
    out = capsys.readouterr().out
    # Strip ALL ANSI CSI sequences (colours, cursor motion, clear-line),
    # not just SGR ``m`` — ``\033[2K`` is the clear-line we emit before
    # the verdict and it would otherwise show up as visible characters.
    import re
    plain = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", out)
    verdict_line = next(
        (line for line in plain.splitlines() if "On the latest version" in line),
        None,
    )
    assert verdict_line is not None
    # ok() format from log.py: ``  ✓  <msg>`` — 2 spaces, glyph, 2 spaces.
    assert verdict_line.startswith("  ✓  "), (
        f"verdict line indent drifted: {verdict_line!r}. Must match ok() "
        f"output (two spaces, glyph, two spaces) or it stops aligning with "
        f"the surrounding install step output."
    )


def test_check_for_updates_does_not_sleep_in_silent_mode(
        monkeypatch, cli_module):
    """Silent / verbose modes must not pause — they're scripted (CI,
    --check-update one-shots) and a 2-second hang would be an annoyance."""
    monkeypatch.setattr(cli_module, "read_version", lambda: "0.8.0")
    monkeypatch.setattr(cli_module, "fetch_latest_release", lambda **_: "0.8.0")
    sleeps: list[float] = []
    monkeypatch.setattr(cli_module.time, "sleep", sleeps.append)

    cli_module.check_for_updates(verbose=True)
    cli_module.check_for_updates(verbose=False)
    assert sleeps == []


# ── root precondition + privilege drop ───────────────────────────────────
def test_require_root_refuses_when_euid_is_not_zero(monkeypatch, capsys, cli_module):
    """The whole point of the precondition: bail BEFORE doing anything
    if uninstall wasn't launched via ``sudo ./uninstall``. Single
    actionable error message, no banner, no tracker side effects, no
    sudo prompts that could trigger pam_faillock."""
    monkeypatch.setattr(cli_module.os, "geteuid", lambda: 1000)
    assert cli_module._require_root_and_drop_to_user() is False
    err = capsys.readouterr().err
    assert "Uninstall must be run as root" in err
    assert "sudo ./uninstall" in err


def test_require_root_refuses_when_sudo_user_missing(monkeypatch, capsys, cli_module):
    """``sudo ./uninstall`` always sets ``SUDO_USER``. If we are root with
    no SUDO_USER, the script was started directly as the root login
    (``su -`` then ``./uninstall``) — refuse, because there's no real user
    to drop privileges to and writes would land owned by root."""
    monkeypatch.setattr(cli_module.os, "geteuid", lambda: 0)
    monkeypatch.delenv("SUDO_USER", raising=False)
    monkeypatch.delenv("SUDO_UID", raising=False)
    monkeypatch.delenv("SUDO_GID", raising=False)
    assert cli_module._require_root_and_drop_to_user() is False
    err = capsys.readouterr().err
    assert "Could not determine the invoking user" in err


def test_require_root_drops_privileges_and_sets_home(monkeypatch, cli_module, tmp_path):
    """Happy path: euid is 0, SUDO_* present. The function:
       1. updates HOME / USER / LOGNAME so user-side writes land under
          the invoking user's home;
       2. calls setegid then seteuid (in that order — the gid drop has
          to happen before the uid drop to keep the privilege to drop
          gid in the first place)."""
    fake_home = tmp_path / "lester"
    fake_home.mkdir()

    # Pre-register HOME / USER / LOGNAME with monkeypatch so pytest
    # auto-restores their pre-test values on teardown — otherwise the
    # function-under-test's direct ``os.environ[...] = ...`` writes
    # leak into every later test in the session.
    monkeypatch.setenv("HOME", "/will-be-overwritten")
    monkeypatch.setenv("USER", "will-be-overwritten")
    monkeypatch.setenv("LOGNAME", "will-be-overwritten")

    monkeypatch.setattr(cli_module.os, "geteuid", lambda: 0)
    monkeypatch.setenv("SUDO_USER", "lester")
    monkeypatch.setenv("SUDO_UID", "1000")
    monkeypatch.setenv("SUDO_GID", "1000")

    import pwd
    real_pwent = pwd.getpwuid(os.geteuid())

    class FakePwent:
        pw_dir = str(fake_home)

    monkeypatch.setattr(pwd, "getpwuid", lambda uid: FakePwent if uid == 1000 else real_pwent)

    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(cli_module.os, "setegid", lambda gid: calls.append(("setegid", gid)))
    monkeypatch.setattr(cli_module.os, "seteuid", lambda uid: calls.append(("seteuid", uid)))

    assert cli_module._require_root_and_drop_to_user() is True
    assert os.environ["HOME"] == str(fake_home)
    assert os.environ["USER"] == "lester"
    assert os.environ["LOGNAME"] == "lester"
    # gid first, then uid — order matters for the privilege drop.
    assert calls == [("setegid", 1000), ("seteuid", 1000)]


def test_run_install_does_not_require_root(monkeypatch, cli_module):
    called = []
    monkeypatch.setattr(cli_module, "_require_root_and_drop_to_user",
                        lambda: called.append(True) or False)
    monkeypatch.setattr(cli_module, "parse_args", lambda _argv: type(
        "Parsed", (), {
            "help": False,
            "check_update": False,
            "do_save": False,
            "do_reset": False,
            "only_mode": False,
            "theme_mode": None,
            "cli_overrides": {},
        })())
    monkeypatch.setattr(cli_module, "load_features", lambda: {"theme_mode": "auto"})
    monkeypatch.setattr(cli_module, "apply_overrides", lambda feat, _parsed: feat)
    monkeypatch.setattr(cli_module, "export_env", lambda _feat: None)
    monkeypatch.setattr(cli_module, "SRC_DIR", Path("/definitely/missing"))

    assert cli_module.run_install([]) == 1
    assert called == []


def test_require_root_falls_back_when_pwd_lookup_fails(
        monkeypatch, cli_module):
    """If ``pwd.getpwuid`` raises (synthesised UID, sandbox, etc.), still
    succeed with a best-effort ``/home/<user>`` path so the install can
    proceed for testing / containerised setups."""
    monkeypatch.setenv("HOME", "/will-be-overwritten")
    monkeypatch.setenv("USER", "will-be-overwritten")
    monkeypatch.setenv("LOGNAME", "will-be-overwritten")

    monkeypatch.setattr(cli_module.os, "geteuid", lambda: 0)
    monkeypatch.setenv("SUDO_USER", "ghost")
    monkeypatch.setenv("SUDO_UID", "60000")
    monkeypatch.setenv("SUDO_GID", "60000")

    import pwd

    def boom(_uid):
        raise KeyError("no such uid")

    monkeypatch.setattr(pwd, "getpwuid", boom)
    monkeypatch.setattr(cli_module.os, "setegid", lambda gid: None)
    monkeypatch.setattr(cli_module.os, "seteuid", lambda uid: None)

    assert cli_module._require_root_and_drop_to_user() is True
    assert os.environ["HOME"] == "/home/ghost"
