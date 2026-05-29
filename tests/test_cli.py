"""CLI install/uninstall: argument parsing, install order, and the
root-precondition that gates every run.

Previously ~38 tests, mostly cosmetic banner behaviour (clear-line
escapes, pause durations, indent column alignment, blank-line
suppression) plus heavily-mocked GitHub fetch tests for the
update-check banner. Those were pinning UI choices that any
terminal-output refresh would have to update, with no impact on
whether the install actually succeeds.

What's kept: behaviour the install loop depends on — the root /
privilege-drop gate (catches the v0.8.6-era sudoless-install
regression), install-step ordering (the dependency graph between
steps), semver parsing (used to decide if a tag is newer), and
basic argv parsing.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture
def cli_module():
    import cli
    return cli


# ── argv parsing ──────────────────────────────────────────────────────


def test_parse_args_recognizes_check_update(cli_module):
    assert cli_module.parse_args(["--check-update"]).check_update is True


def test_parse_args_default_check_update_false(cli_module):
    assert cli_module.parse_args([]).check_update is False


# ── install order — the inter-step dependency graph ───────────────────


def test_install_order_puts_core_theme_steps_before_optional_integrations(cli_module):
    """The install loop walks INSTALL_ORDER linearly. Steps that produce
    artefacts depended on by later steps must come first. The original
    bug this guards against: layout ran before plasmoids, so the JS
    layout script couldn't find the plasmoid plugins it tried to add.
    Reordering this list silently breaks the post-install panel."""
    order = cli_module.INSTALL_ORDER
    assert order.index("global_theme") < order.index("plasmoids")
    assert order.index("wallpapers") < order.index("plasmoids")
    assert order.index("color_schemes") < order.index("wallpapers")
    assert order.index("plasma_theme") < order.index("nautilus")
    assert order.index("global_theme") < order.index("portals")
    assert order.index("nautilus") < order.index("portals")


# ── semver — used by the update checker to compare local vs latest ────


@pytest.mark.parametrize("raw,expected", [
    ("0.8.0",          (0, 8, 0)),
    ("1.2.3",          (1, 2, 3)),
    ("v0.8.0",         (0, 8, 0)),
    ("1.0.0-rc1",      (1, 0, 0)),
    ("",               (0, 0, 0)),
    ("garbage",        (0, 0, 0)),
])
def test_parse_semver(cli_module, raw, expected):
    assert cli_module.parse_semver(raw) == expected


def test_parse_semver_orders_correctly(cli_module):
    """The tuple comparison is the whole point: a string compare would
    say '0.7.14' < '0.7.9' (lexicographic). Real bug shape: update
    checker would say a newer release is older because of the string
    compare."""
    assert cli_module.parse_semver("v0.8.0") > cli_module.parse_semver("0.7.14")
    assert cli_module.parse_semver("0.7.14") > cli_module.parse_semver("0.7.9")


# ── root precondition + privilege drop ────────────────────────────────


def test_require_root_refuses_when_euid_is_not_zero(monkeypatch, capsys, cli_module):
    """v0.10: install + uninstall require sudo upfront. Bail BEFORE
    doing anything (no banner, no tracker writes, no sudo prompts that
    could trigger pam_faillock cascades on terminals where sudo can't
    read the password)."""
    monkeypatch.setattr(cli_module.os, "geteuid", lambda: 1000)

    assert cli_module._require_root_and_drop_to_user("install") is False
    err = capsys.readouterr().err
    assert "Install must be run as root" in err
    assert "sudo ./install" in err

    assert cli_module._require_root_and_drop_to_user("uninstall") is False
    err = capsys.readouterr().err
    assert "Uninstall must be run as root" in err


def test_require_root_refuses_when_sudo_user_missing(monkeypatch, capsys, cli_module):
    """``sudo ./install`` always sets SUDO_USER. Root with no SUDO_USER
    means the user did ``su -`` then ``./install`` — refuse, because
    there is no real user to drop privileges to and writes would land
    owned by root."""
    monkeypatch.setattr(cli_module.os, "geteuid", lambda: 0)
    monkeypatch.delenv("SUDO_USER", raising=False)
    monkeypatch.delenv("SUDO_UID", raising=False)
    monkeypatch.delenv("SUDO_GID", raising=False)
    assert cli_module._require_root_and_drop_to_user() is False
    assert "Could not determine the invoking user" in capsys.readouterr().err


def test_require_root_drops_privileges_in_correct_order(monkeypatch, cli_module, tmp_path):
    """Happy path: setegid MUST come before seteuid. If we drop the uid
    first we lose the privilege required to drop the gid. Linux
    enforces this and would silently leave the gid as 0 — a real
    privilege-escalation bug shape (writes land with root group)."""
    fake_home = tmp_path / "lester"
    fake_home.mkdir()

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

    monkeypatch.setattr(pwd, "getpwuid",
                        lambda uid: FakePwent if uid == 1000 else real_pwent)

    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(cli_module.os, "setegid",
                        lambda gid: calls.append(("setegid", gid)))
    monkeypatch.setattr(cli_module.os, "seteuid",
                        lambda uid: calls.append(("seteuid", uid)))

    assert cli_module._require_root_and_drop_to_user() is True
    assert os.environ["HOME"] == str(fake_home)
    assert os.environ["USER"] == "lester"
    assert os.environ["LOGNAME"] == "lester"
    assert calls == [("setegid", 1000), ("seteuid", 1000)]


def test_run_install_requires_root(monkeypatch, cli_module):
    """v0.10 inverts the v0.8.6-era ``test_run_install_does_not_require_root``:
    sudoless install was the regression that left the dock + global
    menu unloaded under user paths Qt6 doesn't search. ``run_install``
    must exit non-zero before touching any apply path when not root."""
    called: list[str] = []
    monkeypatch.setattr(cli_module, "_require_root_and_drop_to_user",
                        lambda op="install": called.append(op) or False)
    monkeypatch.setattr(cli_module, "parse_args", lambda _argv: type(
        "Parsed", (), {
            "help": False,
            "check_update": False,
            "preflight_only": False,
            "do_save": False,
            "do_reset": False,
            "only_mode": False,
            "theme_mode": None,
            "cli_overrides": {},
        })())
    apply_overrides_called: list[bool] = []
    monkeypatch.setattr(cli_module, "apply_overrides",
                        lambda feat, _parsed: apply_overrides_called.append(True) or feat)

    assert cli_module.run_install([]) == 1
    assert called == ["install"]
    assert apply_overrides_called == []
