"""Tests for the install/uninstall CLI: argument parsing, sudo
preauth, GitHub version checker."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

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


# ── sudo priming (auth + keepalive in one place) ────────────────────────
class _FakeRunResult:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr


class _FakeThread:
    instances: list["_FakeThread"] = []

    def __init__(self, *_a, **_kw):
        self.started = False
        _FakeThread.instances.append(self)

    def start(self):
        self.started = True


@pytest.fixture
def fake_thread(monkeypatch, cli_module):
    _FakeThread.instances.clear()
    monkeypatch.setattr(cli_module.threading, "Thread", _FakeThread)
    monkeypatch.setattr(cli_module.atexit, "register", lambda *_: None)
    return _FakeThread


def test_prime_sudo_returns_true_without_sudo(monkeypatch, cli_module, fake_thread):
    """If sudo isn't installed at all, install can still proceed for
    user-only steps — return True so confirm() lets us through."""
    monkeypatch.setattr(cli_module.shutil, "which", lambda _: None)
    assert cli_module._prime_sudo() is True
    assert all(not t.started for t in fake_thread.instances)


def test_prime_sudo_reads_password_via_getpass_then_pipes_to_sudo(
        monkeypatch, cli_module, fake_thread):
    """Reading the password ourselves bypasses sudo's PAM conversation,
    which is the bit that breaks under VSCode integrated terminals etc."""
    import getpass as _gp

    monkeypatch.setattr(cli_module.shutil, "which", lambda _: "/usr/bin/sudo")
    monkeypatch.setattr(cli_module.subprocess, "run",
                        lambda *_a, **_kw: _FakeRunResult(0))
    monkeypatch.setattr(_gp, "getpass", lambda *_a, **_kw: "hunter2")

    runs: list[tuple] = []

    def fake_run(cmd, **kw):
        runs.append((tuple(cmd), kw.get("input"), kw.get("text")))
        return _FakeRunResult(0)

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    assert cli_module._prime_sudo() is True
    auth_calls = [r for r in runs if "sudo" in r[0] and "-S" in r[0]]
    assert len(auth_calls) == 1
    cmd, stdin, text = auth_calls[0]
    assert cmd == ("sudo", "-S", "-v")
    # Password must end with newline so sudo -S commits the line.
    assert stdin == "hunter2\n"
    assert text is True
    # Keepalive thread must be started exactly once on success.
    assert sum(t.started for t in fake_thread.instances) == 1


def test_prime_sudo_retries_on_wrong_password_then_succeeds(
        monkeypatch, cli_module, fake_thread):
    import getpass as _gp

    monkeypatch.setattr(cli_module.shutil, "which", lambda _: "/usr/bin/sudo")
    passwords = iter(["wrong1", "right"])
    monkeypatch.setattr(_gp, "getpass", lambda *_a, **_kw: next(passwords))

    results = iter([
        _FakeRunResult(1, "Sorry, try again."),
        _FakeRunResult(0),
    ])

    def fake_run(cmd, **_kw):
        if "sudo" in cmd and "-S" in cmd:
            return next(results)
        return _FakeRunResult(0)

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)
    assert cli_module._prime_sudo() is True
    assert sum(t.started for t in fake_thread.instances) == 1


def test_prime_sudo_gives_up_after_three_wrong(monkeypatch, cli_module, fake_thread):
    """Match sudo's classic 3-tries default — but each try is a fresh
    Python read, so we can never trip ``conversation failed`` mid-prompt."""
    import getpass as _gp

    monkeypatch.setattr(cli_module.shutil, "which", lambda _: "/usr/bin/sudo")
    monkeypatch.setattr(_gp, "getpass", lambda *_a, **_kw: "wrong")

    sudo_calls: list = []

    def fake_run(cmd, **_kw):
        if "sudo" in cmd and "-S" in cmd:
            sudo_calls.append(cmd)
            return _FakeRunResult(1, "Sorry, try again.")
        return _FakeRunResult(0)

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)
    assert cli_module._prime_sudo() is False
    # Three tries, no more, no less. And the keepalive must NEVER start
    # on a failed auth — otherwise the daemon thread would fire
    # ``sudo -n -v`` every 60s and add to the faillock count silently.
    assert len(sudo_calls) == 3
    assert all(not t.started for t in fake_thread.instances)


def test_prime_sudo_aborts_immediately_on_keyboard_interrupt(
        monkeypatch, cli_module, fake_thread):
    import getpass as _gp

    monkeypatch.setattr(cli_module.shutil, "which", lambda _: "/usr/bin/sudo")

    def raise_kb(*_a, **_kw): raise KeyboardInterrupt()

    monkeypatch.setattr(_gp, "getpass", raise_kb)

    sudo_calls: list = []

    def fake_run(cmd, **_kw):
        if "sudo" in cmd:
            sudo_calls.append(cmd)
        return _FakeRunResult(0)

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    assert cli_module._prime_sudo() is False
    # Ctrl+C before typing anything must NOT result in a sudo call —
    # otherwise we'd send an empty string as the password and PAM would
    # count that toward the faillock threshold.
    assert sudo_calls == []
    assert all(not t.started for t in fake_thread.instances)


def test_prime_sudo_does_not_retry_on_non_password_error(
        monkeypatch, cli_module, fake_thread):
    """Sudoers config errors, locked accounts, missing tty in -S mode —
    none of those get fixed by retrying. Bail out fast so the user can
    see the real error instead of three round-trips of the same."""
    import getpass as _gp

    monkeypatch.setattr(cli_module.shutil, "which", lambda _: "/usr/bin/sudo")
    monkeypatch.setattr(_gp, "getpass", lambda *_a, **_kw: "anything")

    sudo_calls: list = []

    def fake_run(cmd, **_kw):
        if "sudo" in cmd and "-S" in cmd:
            sudo_calls.append(cmd)
            return _FakeRunResult(1, "user lester is not in the sudoers file.")
        return _FakeRunResult(0)

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)
    assert cli_module._prime_sudo() is False
    assert len(sudo_calls) == 1
