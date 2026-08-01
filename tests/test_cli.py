"""CLI install/uninstall: argument parsing, install order, and the
root-precondition that gates every run.

Only behaviour the install loop depends on belongs here — the root /
privilege-drop gate (a sudoless install leaves the dock + global
menu unloaded), install-step ordering (the dependency graph between
steps), semver parsing (used to decide if a tag is newer), and
basic argv parsing. Don't pin cosmetic banner behaviour: that's UI
choice, not install correctness.
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


def test_parse_args_recognizes_one_shot_wallpaper_reset(cli_module):
    parsed = cli_module.parse_args(["--reset-wallpapers"])
    assert parsed.reset_wallpapers is True


def test_existing_install_detects_current_state_marker(
        cli_module, monkeypatch, tmp_path):
    home = tmp_path / "home"
    marker = home / ".local/state/mac-tahoe-liquid-kde/wallpapers.json"
    marker.parent.mkdir(parents=True)
    marker.write_text("{}\n")
    monkeypatch.setenv("HOME", str(home))

    assert cli_module._theme_is_already_installed() is True


def test_existing_install_detects_legacy_applet_without_state(
        cli_module, monkeypatch, tmp_path):
    home = tmp_path / "home"
    config = home / ".config"
    config.mkdir(parents=True)
    (config / "plasma-org.kde.plasma.desktop-appletsrc").write_text(
        "plugin=org.kde.mac-tahoe-liquid-kde.launcher\n")
    monkeypatch.setenv("HOME", str(home))

    assert cli_module._theme_is_already_installed() is True


# ── install order — the inter-step dependency graph ───────────────────


def test_install_order_puts_core_theme_steps_before_optional_integrations(cli_module):
    """The install loop walks INSTALL_ORDER linearly. Steps that produce
    artefacts depended on by later steps must come first. Failure
    mode: if layout runs before plasmoids, the JS layout script
    can't find the plasmoid plugins it tries to add.
    Reordering this list silently breaks the post-install panel."""
    order = cli_module.INSTALL_ORDER
    assert order.index("global_theme") < order.index("plasmoids")
    assert order.index("wallpapers") < order.index("plasmoids")
    assert order.index("sounds") < order.index("plasmoids")
    assert order.index("color_schemes") < order.index("wallpapers")
    assert order.index("plasma_theme") < order.index("nautilus")
    assert order.index("global_theme") < order.index("portals")
    assert order.index("nautilus") < order.index("portals")
    assert order.index("acrylic_glass") < order.index("rounded_corners")


def test_rounded_corners_flag_is_first_class(cli_module):
    parsed = cli_module.parse_args(["--no-rounded-corners"])
    assert parsed.cli_overrides == {"rounded_corners": False}
    assert cli_module.DEFAULT_FEATURES["rounded_corners"] is True


def test_online_download_failure_skips_feature_without_blocking(
        cli_module, monkeypatch):
    feature = "rounded_corners"

    class _OnlineStep:
        @staticmethod
        def download_ready():
            return False

    feat = {feature: True}
    warnings: list[str] = []
    monkeypatch.setenv("FEAT_ROUNDED_CORNERS", "true")
    monkeypatch.setattr(cli_module, "_download_features", lambda _: [feature])
    monkeypatch.setattr(cli_module, "run_phase", lambda *args: False)
    monkeypatch.setattr(cli_module, "step_module", lambda _: _OnlineStep)
    monkeypatch.setattr(cli_module, "warn", warnings.append)

    assert cli_module._run_optional_downloads(feat) is True
    assert feat[feature] is False
    assert cli_module.os.environ["FEAT_ROUNDED_CORNERS"] == "false"
    assert any("install continues" in message for message in warnings)


def test_successful_online_download_keeps_feature_enabled(
        cli_module, monkeypatch):
    feature = "rounded_corners"

    class _OnlineStep:
        @staticmethod
        def download_ready():
            return True

    feat = {feature: True}
    monkeypatch.setenv("FEAT_ROUNDED_CORNERS", "true")
    monkeypatch.setattr(cli_module, "_download_features", lambda _: [feature])
    monkeypatch.setattr(cli_module, "run_phase", lambda *args: True)
    monkeypatch.setattr(cli_module, "step_module", lambda _: _OnlineStep)

    assert cli_module._run_optional_downloads(feat) is True
    assert feat[feature] is True


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
    """Install + uninstall require sudo upfront. Bail BEFORE
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
    monkeypatch.setenv("XDG_CONFIG_HOME", "/root/.config")
    monkeypatch.setenv("XDG_DATA_HOME", "/root/.local/share")
    monkeypatch.setenv("XDG_CACHE_HOME", "/root/.cache")
    monkeypatch.setenv("XDG_STATE_HOME", "/root/.local/state")
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
    assert os.environ["XDG_CONFIG_HOME"] == str(fake_home / ".config")
    assert os.environ["XDG_DATA_HOME"] == str(fake_home / ".local/share")
    assert os.environ["XDG_CACHE_HOME"] == str(fake_home / ".cache")
    assert os.environ["XDG_STATE_HOME"] == str(fake_home / ".local/state")
    assert calls == [("setegid", 1000), ("seteuid", 1000)]


def test_run_install_requires_root(monkeypatch, cli_module):
    """A sudoless install leaves the dock + global menu unloaded
    under user paths Qt6 doesn't search. ``run_install`` must exit
    non-zero before touching any apply path when not root."""
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


# ── auto-update on install (pull newer release, re-exec) ──────────────


def test_auto_update_skips_when_recursion_guard_set(cli_module, monkeypatch):
    """After a successful pull we re-exec with MAC_TAHOE_UPDATED=1; that
    second run must NOT pull/re-exec again — it just installs."""
    monkeypatch.setenv("MAC_TAHOE_UPDATED", "1")
    execv_called: list = []
    monkeypatch.setattr(cli_module.os, "execv",
                        lambda *a: execv_called.append(a))
    # _git must never be consulted on the guarded run.
    monkeypatch.setattr(cli_module, "_git",
                        lambda *a, **k: pytest.fail("git touched on guarded run"))

    cli_module.auto_update_and_reexec([])
    assert execv_called == []


def test_auto_update_bails_when_not_a_clean_git_checkout(cli_module, monkeypatch):
    """A tarball install / dirty tree must fall back to installing the
    current version, never pull."""
    monkeypatch.delenv("MAC_TAHOE_UPDATED", raising=False)
    monkeypatch.setattr(cli_module, "_repo_is_clean_git_checkout", lambda: False)
    pull_calls: list = []
    monkeypatch.setattr(cli_module, "_git",
                        lambda *a, **k: pull_calls.append(a))
    execv_called: list = []
    monkeypatch.setattr(cli_module.os, "execv",
                        lambda *a: execv_called.append(a))

    cli_module.auto_update_and_reexec([])
    assert pull_calls == []      # never pulled
    assert execv_called == []    # never re-exec'd


def test_auto_update_bails_when_pull_fails(cli_module, monkeypatch):
    """If git pull fails (conflict, offline, detached), install the
    current version instead of re-exec'ing into a half-updated tree."""
    monkeypatch.delenv("MAC_TAHOE_UPDATED", raising=False)
    monkeypatch.setattr(cli_module, "_repo_is_clean_git_checkout", lambda: True)

    class _Fail:
        returncode = 1
        stderr = "fatal: could not fast-forward"

    monkeypatch.setattr(cli_module, "_git", lambda *a, **k: _Fail())
    execv_called: list = []
    monkeypatch.setattr(cli_module.os, "execv",
                        lambda *a: execv_called.append(a))

    cli_module.auto_update_and_reexec([])
    assert execv_called == []
    assert os.environ.get("MAC_TAHOE_UPDATED") != "1"  # guard not leaked


def test_auto_update_pulls_and_reexecs_install(cli_module, monkeypatch):
    """Happy path: clean checkout + successful pull → set the recursion
    guard and re-exec ./install with the same argv."""
    monkeypatch.delenv("MAC_TAHOE_UPDATED", raising=False)
    monkeypatch.setattr(cli_module, "_repo_is_clean_git_checkout", lambda: True)

    class _Ok:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(cli_module, "_git", lambda *a, **k: _Ok())

    execv_args: list = []
    monkeypatch.setattr(cli_module.os, "execv",
                        lambda path, argv: execv_args.append((path, argv)))

    cli_module.auto_update_and_reexec(["--dark", "--no-gtk"])

    assert os.environ.get("MAC_TAHOE_UPDATED") == "1"  # guard set before exec
    assert len(execv_args) == 1
    path, argv = execv_args[0]
    assert path.endswith("/install")
    # argv[0] is the program, the install flags follow verbatim.
    assert argv[1:] == ["--dark", "--no-gtk"]


# ── _check_deps: probe each package, install ONLY the missing ones ──────


@pytest.fixture
def _deps_env(monkeypatch, cli_module):
    import distro
    monkeypatch.setattr(cli_module, "_BASE_DEPS", [("cmake", "cmake")])
    monkeypatch.setattr(cli_module, "step_exists", lambda feature: True)
    monkeypatch.setattr(cli_module, "should_process",
                        lambda feature, feat: feat.get(feature, True))
    monkeypatch.setattr(cli_module, "step_deps", lambda feature: [
        ("vulkan-loader-cmake",  "vulkan-icd-loader"),
        ("vulkan-headers-cmake", "vulkan-headers"),
    ])
    monkeypatch.setattr(distro, "package_manager_install_cmd",
                        lambda: ["package-manager", "install"])
    monkeypatch.setattr(distro, "package_for", lambda cmd, pkg=None: pkg or cmd)
    return distro


def test_check_deps_installs_only_missing_packages(monkeypatch, cli_module, _deps_env):
    # vulkan-headers absent, the rest present → only it gets installed.
    monkeypatch.setattr(_deps_env, "package_installed",
                        lambda pkg: pkg != "vulkan-headers")
    installed: list[tuple] = []
    monkeypatch.setattr(cli_module, "pkg_sync_install",
                        lambda *pkgs: installed.append(pkgs) or True)

    assert cli_module._check_deps({"acrylic_glass": True}) is True

    assert installed == [("vulkan-headers",)]


def test_check_deps_installs_nothing_when_all_present(monkeypatch, cli_module, _deps_env):
    # All present → no install call at all (no -Sy, no upgrade, no conflict).
    monkeypatch.setattr(_deps_env, "package_installed", lambda pkg: True)
    called = []
    monkeypatch.setattr(cli_module, "pkg_sync_install",
                        lambda *pkgs: called.append(pkgs) or True)

    assert cli_module._check_deps({"acrylic_glass": True}) is True

    assert called == []


def test_check_deps_rejects_unsupported_package_manager_before_translation(
        monkeypatch, cli_module, _deps_env):
    support_checks: list[bool] = []

    def unsupported():
        support_checks.append(True)
        raise _deps_env.UnsupportedDistroError("unsupported test distro")

    monkeypatch.setattr(_deps_env, "package_manager_install_cmd", unsupported)
    monkeypatch.setattr(
        _deps_env, "package_for",
        lambda *_args: pytest.fail("package translation ran before support check"),
    )
    monkeypatch.setattr(
        _deps_env, "package_installed",
        lambda _pkg: pytest.fail("package probe ran for unsupported distro"),
    )
    monkeypatch.setattr(
        cli_module, "pkg_sync_install",
        lambda *_pkgs: pytest.fail("package install ran for unsupported distro"),
    )
    monkeypatch.setattr(cli_module, "fail", lambda _message: None)

    assert cli_module._check_deps({"acrylic_glass": True}) is False
    assert support_checks == [True]


def test_check_deps_resolves_every_package_before_any_probe(
        monkeypatch, cli_module, _deps_env):
    monkeypatch.setattr(cli_module, "_BASE_DEPS", [
        ("aaa-good-command", "good-package"),
        ("zzz-unmapped-command", "arch-only-package"),
    ])
    monkeypatch.setattr(cli_module, "INSTALL_ORDER", [])
    probes: list[str] = []
    installs: list[tuple[str, ...]] = []

    def package_for(command, fallback_pkg=None):
        if command == "zzz-unmapped-command":
            raise _deps_env.PackageMappingError("missing package mapping")
        return fallback_pkg or command

    monkeypatch.setattr(_deps_env, "package_for", package_for)
    monkeypatch.setattr(
        _deps_env, "package_installed",
        lambda pkg: probes.append(pkg) or False,
    )
    monkeypatch.setattr(
        cli_module, "pkg_sync_install",
        lambda *pkgs: installs.append(pkgs) or True,
    )
    monkeypatch.setattr(cli_module, "fail", lambda _message: None)

    assert cli_module._check_deps({}) is False
    assert probes == []
    assert installs == []


def test_check_deps_returns_false_when_missing_package_install_fails(
        monkeypatch, cli_module, _deps_env):
    monkeypatch.setattr(
        _deps_env, "package_installed",
        lambda pkg: pkg != "cmake",
    )
    attempts: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        cli_module, "pkg_sync_install",
        lambda *pkgs: attempts.append(pkgs) or False,
    )
    monkeypatch.setattr(cli_module, "fail", lambda _message: None)

    assert cli_module._check_deps({"acrylic_glass": True}) is False
    assert attempts == [("cmake",)]


def test_check_deps_collects_deps_from_separately_run_steps(
        monkeypatch, cli_module, _deps_env):
    monkeypatch.setattr(cli_module, "_BASE_DEPS", [])
    deps_calls: list[str] = []
    probes: list[str] = []

    def deps_for(feature):
        deps_calls.append(feature)
        if feature in {"theme_switch", "oled_care"}:
            return [(f"{feature}-command", f"{feature}-package")]
        return []

    monkeypatch.setattr(cli_module, "step_deps", deps_for)
    monkeypatch.setattr(
        _deps_env, "package_installed",
        lambda pkg: probes.append(pkg) or True,
    )
    monkeypatch.setattr(
        cli_module, "pkg_sync_install",
        lambda *_pkgs: pytest.fail("present dependencies were reinstalled"),
    )

    assert cli_module._check_deps({
        "theme_switch": True,
        "oled_care": True,
    }) is True
    assert {"theme_switch", "oled_care"} <= set(deps_calls)
    assert set(probes) == {
        "theme_switch-package",
        "oled_care-package",
    }


def test_run_install_body_stops_before_download_when_deps_fail(
        monkeypatch, cli_module):
    monkeypatch.setattr(cli_module, "run_preflight", lambda _operation: True)
    monkeypatch.setattr(cli_module, "verify_plasma", lambda: True)
    monkeypatch.setattr(cli_module, "_check_deps", lambda _feat: False)
    monkeypatch.setattr(
        cli_module, "_run_optional_downloads",
        lambda _feat: pytest.fail("download ran after dependency failure"),
    )
    monkeypatch.setattr(
        cli_module, "_run_builds_or_abort",
        lambda _feat: pytest.fail("build ran after dependency failure"),
    )
    monkeypatch.setattr(cli_module, "fail", lambda _message: None)

    assert cli_module._run_install_body({}) == 1


# ── globalmenu as a first-class feature ──────────────────────────────


def test_globalmenu_flags_are_parsed(cli_module):
    assert cli_module.parse_args(["--no-globalmenu"]).cli_overrides == \
        {"globalmenu": False}
    assert cli_module.parse_args(["--globalmenu"]).cli_overrides == \
        {"globalmenu": True}


def test_globalmenu_governed_by_its_own_flag(cli_module):
    """If should_process defers to the plasmoids shortcut,
    --no-globalmenu parses fine and then gets ignored. Each feature
    must obey exactly its own entry."""
    assert cli_module.should_process(
        "globalmenu", {"globalmenu": False, "plasmoids": True}) is False
    assert cli_module.should_process(
        "globalmenu", {"globalmenu": True, "plasmoids": False}) is True


def test_only_globalmenu_selects_just_globalmenu(cli_module):
    parsed = cli_module.parse_args(["--only", "--globalmenu"])
    feat = cli_module.apply_overrides(dict(cli_module.DEFAULT_FEATURES), parsed)
    assert cli_module.should_process("globalmenu", feat) is True
    assert cli_module.should_process("plasmoids", feat) is False
    assert cli_module.should_process("icons", feat) is False
