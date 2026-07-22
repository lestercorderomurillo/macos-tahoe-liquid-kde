"""Portability + hang-safety tests for the apply step: the live
KWin-reconfigure guard resolves qdbus via utils.qdbus_cmd() (Fedora's
qdbus-qt6), and _run_live bounds its calls with a timeout.
"""

import subprocess
from pathlib import Path

import utils
import steps.apply as apply


def _force_qdbus_binaries(monkeypatch, present):
    """Pin which qdbus binary names ``have()`` reports and drain the
    module-level qdbus cache so the new set is actually consulted.
    ``apply.qdbus_cmd`` is ``utils.qdbus_cmd``, which reads ``utils.have``
    and ``utils._QDBUS_CACHE`` — patch both on utils."""
    monkeypatch.setattr(utils, "have", lambda cmd: cmd in present)
    monkeypatch.setattr(utils, "_QDBUS_CACHE", None)


def test_reconfigure_guard_passes_under_fedora_binary_name(monkeypatch):
    # The exact Fedora regression: only qdbus-qt6 is on PATH.
    _force_qdbus_binaries(monkeypatch, {"qdbus-qt6"})

    # The old guard expression would have been False here...
    assert (utils.have("qdbus6") or utils.have("qdbus")) is False
    # ...but the new guard resolves the binary and lets the reconfigure run.
    assert apply.qdbus_cmd() is not None


def test_reconfigure_guard_passes_under_qt5_fallback_name(monkeypatch):
    _force_qdbus_binaries(monkeypatch, {"qdbus"})
    assert apply.qdbus_cmd() is not None


def test_reconfigure_guard_blocks_when_no_qdbus_present(monkeypatch):
    _force_qdbus_binaries(monkeypatch, set())
    assert apply.qdbus_cmd() is None


def test_run_live_caps_calls_at_the_shared_timeout(monkeypatch):
    # _run_live must pass a timeout (15s, matching qdbus_call) so a stuck
    # KDE endpoint can't hang the installer.
    seen = {}

    def fake_run_user(cmd, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(apply, "run_user", fake_run_user)
    apply._run_live(["kbuildsycoca6", "--noincremental"])

    assert seen["timeout"] == apply._LIVE_APPLY_TIMEOUT


def test_run_live_swallows_timeout(monkeypatch):
    # A TimeoutExpired from the child must not propagate out of _run_live.
    def fake_run_user(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 0))

    monkeypatch.setattr(apply, "run_user", fake_run_user)

    # Must report failure without raising.
    assert apply._run_live(["plasma-apply-wallpaperimage", "/x"]) is False


# ── graceful Plasma restart with hard-stop fallback ──────────────────


def _restart_env(monkeypatch, *, systemd=True):
    import distro

    calls = []
    monkeypatch.setattr(distro, "init_system",
                        lambda: "systemd" if systemd else "openrc")
    monkeypatch.setattr(apply.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(apply, "have", lambda command: command == "kquitapp6")
    monkeypatch.setattr(apply, "_plasma_pids", lambda: {42})
    monkeypatch.setattr(apply, "_wait_for_plasma_start", lambda attempts=30: True)
    monkeypatch.setattr(apply, "ok", lambda message: calls.append(("ok", message)))
    monkeypatch.setattr(apply, "warn",
                        lambda message: calls.append(("warn", message)))
    return calls


def test_restart_prefers_kquitapp_and_never_hard_kills_on_success(monkeypatch):
    calls = _restart_env(monkeypatch)
    commands = []
    monkeypatch.setattr(
        apply, "_run_quick",
        lambda command, **kwargs:
        commands.append(command) or subprocess.CompletedProcess(command, 0),
    )
    monkeypatch.setattr(apply, "_wait_for_old_plasma_exit",
                        lambda pids, attempts=12: True)
    monkeypatch.setattr(
        apply, "_hard_kill_plasma",
        lambda systemd: (_ for _ in ()).throw(
            AssertionError("SIGKILL reached after graceful quit")),
    )
    starts = []
    monkeypatch.setattr(apply, "_start_plasma",
                        lambda systemd: starts.append(systemd) or True)

    apply.restart_plasma()

    assert commands == [["kquitapp6", "plasmashell"]]
    assert starts == [True]
    assert any(kind == "ok" for kind, _ in calls)


def test_restart_uses_systemd_restart_when_kquitapp_fails(monkeypatch):
    _restart_env(monkeypatch)
    commands = []
    monkeypatch.setattr(apply, "_wait_for_old_plasma_exit",
                        lambda pids, attempts=12: True)

    def run(command, **kwargs):
        commands.append(command)
        rc = 1 if command[0] == "kquitapp6" else 0
        return subprocess.CompletedProcess(command, rc)

    monkeypatch.setattr(apply, "_run_quick", run)
    monkeypatch.setattr(
        apply, "_hard_kill_plasma",
        lambda systemd: (_ for _ in ()).throw(
            AssertionError("SIGKILL reached after systemd restart")),
    )
    monkeypatch.setattr(
        apply, "_start_plasma",
        lambda systemd: (_ for _ in ()).throw(
            AssertionError("successful restart must not start twice")),
    )

    apply.restart_plasma()

    assert commands == [
        ["kquitapp6", "plasmashell"],
        ["systemctl", "--user", "restart", "plasma-plasmashell"],
    ]


def test_restart_rejects_false_positive_systemd_restart(monkeypatch):
    _restart_env(monkeypatch)
    monkeypatch.setattr(
        apply, "_run_quick",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0),
    )
    # Both graceful commands report success, but the original PID remains.
    monkeypatch.setattr(apply, "_wait_for_old_plasma_exit",
                        lambda pids, attempts=12: False)
    hard = []
    starts = []
    monkeypatch.setattr(apply, "_hard_kill_plasma",
                        lambda systemd: hard.append(systemd))
    monkeypatch.setattr(apply, "_start_plasma",
                        lambda systemd: starts.append(systemd) or True)

    apply.restart_plasma()

    assert hard == [True]
    assert starts == [True]


def test_restart_hard_kills_only_after_both_graceful_paths_fail(monkeypatch):
    _restart_env(monkeypatch)
    commands = []
    monkeypatch.setattr(
        apply, "_run_quick",
        lambda command, **kwargs:
        commands.append(command) or subprocess.CompletedProcess(command, 1),
    )
    monkeypatch.setattr(apply, "_wait_for_old_plasma_exit",
                        lambda pids, attempts=12: True)
    hard = []
    starts = []
    monkeypatch.setattr(apply, "_hard_kill_plasma",
                        lambda systemd: hard.append(systemd))
    monkeypatch.setattr(apply, "_start_plasma",
                        lambda systemd: starts.append(systemd) or True)

    apply.restart_plasma()

    assert commands[:2] == [
        ["kquitapp6", "plasmashell"],
        ["systemctl", "--user", "restart", "plasma-plasmashell"],
    ]
    assert hard == [True]
    assert starts == [True]


# ── desktop database refresh keeps apps in the launcher after a switch ──


def test_refresh_desktop_database_runs_update_for_both_dirs(monkeypatch, tmp_path):
    # update-desktop-database must run for the user AND system applications
    # dirs — a stale mimeinfo.cache is why apps vanish from the launcher
    # after switching back to the default theme.
    import contextlib
    user_apps = tmp_path / ".local/share/applications"
    user_apps.mkdir(parents=True)
    monkeypatch.setattr(apply, "HOME", tmp_path)
    monkeypatch.setattr(apply, "have", lambda cmd: cmd == "update-desktop-database")
    # Neutralise the real seteuid(0) hop — tests don't run as root.
    monkeypatch.setattr("steps._helpers._as_root", contextlib.nullcontext)

    live_calls: list = []
    monkeypatch.setattr(apply, "_run_live", lambda cmd: live_calls.append(cmd))
    root_calls: list = []
    monkeypatch.setattr(apply.subprocess, "run",
                        lambda cmd, **kw: root_calls.append(cmd))

    apply._refresh_desktop_database()

    assert live_calls == [["update-desktop-database", str(user_apps)]]
    assert root_calls == [["update-desktop-database", "/usr/share/applications"]]


def test_refresh_desktop_database_noop_without_tool(monkeypatch):
    # No update-desktop-database on PATH → do nothing, never raise.
    monkeypatch.setattr(apply, "have", lambda cmd: False)
    called = []
    monkeypatch.setattr(apply, "_run_live", lambda cmd: called.append(cmd))
    apply._refresh_desktop_database()
    assert called == []


# ── icon theme is reset to breeze even when the ICONS feature is OFF ────


def _seed_install_env(monkeypatch, tmp_path):
    """Shrink install() to the theme-switch spawn block: fonts, wallpaper,
    caches, and the KWin tail are stubbed or feature-gated off."""
    switch = tmp_path / ".local/bin/mac-tahoe-theme-switch"
    switch.parent.mkdir(parents=True)
    switch.write_text("#!/bin/sh\n")
    switch.chmod(0o755)
    monkeypatch.setattr(apply, "HOME", tmp_path)
    monkeypatch.setattr(apply, "have", lambda cmd: False)
    monkeypatch.setattr(apply, "feat_enabled",
                        lambda name, default=True: False)
    monkeypatch.setattr(apply, "_flush_caches", lambda: None)
    monkeypatch.setattr(apply, "qdbus_call", lambda *a: True)
    monkeypatch.setattr(
        apply, "reconfigure_kwin_preserving_foreign_effects", lambda: [],
    )
    monkeypatch.setattr(apply.time, "sleep", lambda s: None)
    monkeypatch.delenv("THEME_MODE", raising=False)
    oks: list = []
    warns: list = []
    monkeypatch.setattr(apply, "ok", lambda m: oks.append(m))
    monkeypatch.setattr(apply, "warn", lambda m: warns.append(m))
    return switch, oks, warns


def test_install_oks_theme_applied_only_on_zero_exit(monkeypatch, tmp_path):
    """Issue #37: the switcher spawn must use the dedicated 90s bound
    (its own subcalls are 15-20s each — the old shared 15s cap killed it
    mid-apply) and report ok only on exit 0."""
    switch, oks, warns = _seed_install_env(monkeypatch, tmp_path)
    seen: dict = {}

    def fake_run_user(cmd, **kw):
        seen["cmd"] = cmd
        seen["timeout"] = kw.get("timeout")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(apply, "run_user", fake_run_user)
    apply.install()

    assert seen["cmd"] == [str(switch), "auto", "install"]
    assert seen["timeout"] == apply._THEME_SWITCH_TIMEOUT
    assert any("Theme applied" in m for m in oks)
    assert not any("Theme switch" in m for m in warns)


def test_install_warns_on_nonzero_theme_switch_exit(monkeypatch, tmp_path):
    _, oks, warns = _seed_install_env(monkeypatch, tmp_path)
    monkeypatch.setattr(
        apply, "run_user",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1))
    apply.install()
    assert not any("Theme applied" in m for m in oks)
    assert any("Theme switch failed" in m for m in warns)


def test_install_surfaces_third_party_effect_warning(monkeypatch, tmp_path):
    _, _, warns = _seed_install_env(monkeypatch, tmp_path)
    monkeypatch.setattr(
        apply, "run_user",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 0, stdout="",
            stderr=("theme apply: your KWin effect 'shapecorners' is enabled "
                    "but KWin could not load it after the theme switch.\n"),
        ),
    )

    apply.install()

    assert any("shapecorners" in message for message in warns)


def test_install_warns_when_theme_switch_times_out(monkeypatch, tmp_path):
    _, oks, warns = _seed_install_env(monkeypatch, tmp_path)

    def fake_run_user(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 0))

    monkeypatch.setattr(apply, "run_user", fake_run_user)
    apply.install()
    assert not any("Theme applied" in m for m in oks)
    assert any("Theme switch did not finish" in m for m in warns)


# ── uninstall reports reset/cycle failures instead of silent ok ────────


def _seed_uninstall_env(monkeypatch, tmp_path):
    monkeypatch.setattr(apply, "HOME", tmp_path)
    monkeypatch.setattr(apply, "have", lambda cmd: cmd == "kwriteconfig6")
    monkeypatch.setattr(apply, "kw_write", lambda *a, **k: True)
    monkeypatch.setattr(apply, "feat_enabled",
                        lambda name, default=True: False)
    monkeypatch.setattr(apply, "_scrub_kdedefaults", lambda: None)
    monkeypatch.setattr(apply, "_flush_caches", lambda: None)
    monkeypatch.setattr(apply, "_run_live", lambda cmd: None)
    monkeypatch.setattr(apply, "_live_plasma_ready_quick", lambda: False)
    monkeypatch.setattr(apply, "_current_wallpapers", lambda: [])
    monkeypatch.setattr(apply, "_wallpapers_from_config", lambda: [])
    monkeypatch.setattr(apply, "_apply_wallpaper_snapshot",
                        lambda snapshot: False)
    monkeypatch.setattr(apply, "_write_wallpapers_to_config",
                        lambda snapshot: False)
    # Keep every DBus-facing tail of uninstall() inert.  Individual tests
    # may report a live session to exercise a branch, but that must never
    # let the Breeze look-and-feel reach the maintainer's real desktop.
    monkeypatch.setattr(apply, "_apply_lookandfeel_live", lambda laf: True)
    monkeypatch.setattr(apply, "cycle_widget_style_live", lambda style: True)
    monkeypatch.setattr(apply, "qdbus_cmd", lambda: None)
    oks: list = []
    warns: list = []
    monkeypatch.setattr(apply, "ok", lambda m: oks.append(m))
    monkeypatch.setattr(apply, "warn", lambda m: warns.append(m))
    return oks, warns


def test_uninstall_warns_when_color_reset_fails(monkeypatch, tmp_path):
    """Issue #37: under the sudo'd installer every kwriteconfig6 child hit
    Qt6's setuid abort, the reset silently no-opped, and the step still
    printed 'Color scheme reset'. Failure must warn, never ok."""
    oks, warns = _seed_uninstall_env(monkeypatch, tmp_path)
    monkeypatch.setattr(apply, "reset_kde_color_scheme_config",
                        lambda s: False)
    apply.uninstall()
    assert not any("Color scheme reset" == m for m in oks)
    assert any("Color scheme reset failed" in m for m in warns)


def test_uninstall_oks_color_reset_on_success(monkeypatch, tmp_path):
    oks, warns = _seed_uninstall_env(monkeypatch, tmp_path)
    monkeypatch.setattr(apply, "reset_kde_color_scheme_config",
                        lambda s: True)
    apply.uninstall()
    assert any("Color scheme reset" == m for m in oks)
    assert not any("Color scheme" in m for m in warns)


def test_uninstall_warns_when_widget_cycle_fails(monkeypatch, tmp_path):
    oks, warns = _seed_uninstall_env(monkeypatch, tmp_path)
    monkeypatch.setattr(apply, "reset_kde_color_scheme_config",
                        lambda s: True)
    monkeypatch.setattr(apply, "_live_plasma_ready_quick", lambda: True)
    monkeypatch.setattr(apply, "_apply_lookandfeel_live", lambda laf: True)
    monkeypatch.setattr(apply, "cycle_widget_style_live", lambda t: False)
    monkeypatch.setattr(apply, "qdbus_cmd", lambda: None)
    apply.uninstall()
    assert any("Widget style cycle failed" in m for m in warns)


def test_uninstall_resets_icon_theme_even_when_icons_feature_disabled(
        monkeypatch, tmp_path):
    # The MacTahoe icon dirs get deleted later in the uninstall. If
    # kdeglobals still named them with ICONS off, KDE would log
    # "Icon theme MacTahoeLiquidKde-Icons not found". The reset must be
    # unconditional.
    writes: list = []
    monkeypatch.setattr(apply, "kw_write",
                        lambda *a, **k: writes.append(a) or True)
    monkeypatch.setattr(apply, "have", lambda cmd: cmd == "kwriteconfig6")
    # Every feature flag OFF — including ICONS.
    monkeypatch.setattr(apply, "feat_enabled", lambda name, default=True: False)
    # Stub out everything else uninstall() touches so we isolate the reset.
    monkeypatch.setattr(apply, "_scrub_kdedefaults", lambda: None)
    monkeypatch.setattr(apply, "_flush_caches", lambda: None)
    monkeypatch.setattr(apply, "_run_live", lambda cmd: None)
    monkeypatch.setattr(apply, "reset_kde_color_scheme_config", lambda s: None)
    monkeypatch.setattr(apply, "_live_plasma_ready_quick", lambda: False)
    monkeypatch.setattr(apply, "HOME", tmp_path)

    apply.uninstall()

    icon_resets = [w for w in writes
                   if "Icons" in w and "Theme" in w and "breeze" in w]
    assert icon_resets, "icon theme must be reset to breeze even with ICONS off"


def test_uninstall_prefers_official_icon_and_cursor_tools(monkeypatch,
                                                           tmp_path):
    writes: list = []
    calls: list[list[str]] = []
    monkeypatch.setattr(apply, "HOME", tmp_path)
    monkeypatch.setattr(
        apply, "have",
        lambda cmd: cmd in {"kwriteconfig6", "plasma-apply-cursortheme"},
    )
    changeicons = Path("/usr/lib/plasma-changeicons")
    monkeypatch.setattr(
        apply, "kde_libexec_binary",
        lambda name: changeicons if name == "plasma-changeicons" else None,
    )
    monkeypatch.setattr(
        apply, "feat_enabled",
        lambda name, default=True: name == "CURSORS",
    )
    monkeypatch.setattr(
        apply, "kw_write",
        lambda *a, **k: writes.append(a) or True,
    )
    monkeypatch.setattr(
        apply, "_run_live",
        lambda cmd: calls.append(cmd) or True,
    )
    monkeypatch.setattr(apply, "_live_plasma_ready_quick", lambda: True)
    monkeypatch.setattr(apply, "_scrub_kdedefaults", lambda: None)
    monkeypatch.setattr(apply, "_flush_caches", lambda: None)
    monkeypatch.setattr(apply, "reset_kde_color_scheme_config", lambda s: True)
    monkeypatch.setattr(apply, "_apply_lookandfeel_live", lambda laf: True)
    monkeypatch.setattr(apply, "cycle_widget_style_live", lambda style: True)
    monkeypatch.setattr(apply, "qdbus_cmd", lambda: None)

    apply.uninstall()

    assert [str(changeicons), "breeze"] in calls
    assert ["plasma-apply-cursortheme", "breeze_cursors"] in calls
    assert not any("Icons" in write or "cursorTheme" in write
                   for write in writes)


def test_uninstall_uses_official_icon_and_cursor_tools_before_shell_ready(
        monkeypatch, tmp_path):
    """Issue #60: the helpers also own the on-disk update, so a session
    startup race must not divert uninstall straight to manual INI writes."""
    writes: list = []
    calls: list[list[str]] = []
    monkeypatch.setattr(apply, "HOME", tmp_path)
    monkeypatch.setattr(
        apply, "have",
        lambda cmd: cmd in {"kwriteconfig6", "plasma-apply-cursortheme"},
    )
    changeicons = Path("/usr/lib/plasma-changeicons")
    monkeypatch.setattr(apply, "kde_libexec_binary", lambda _: changeicons)
    monkeypatch.setattr(
        apply, "feat_enabled", lambda name, default=True: name == "CURSORS",
    )
    monkeypatch.setattr(apply, "kw_write", lambda *a, **k: writes.append(a) or True)
    monkeypatch.setattr(apply, "_run_live", lambda cmd: calls.append(cmd) or True)
    monkeypatch.setattr(apply, "_live_plasma_ready_quick", lambda: False)
    monkeypatch.setattr(apply, "_scrub_kdedefaults", lambda: None)
    monkeypatch.setattr(apply, "_flush_caches", lambda: None)
    monkeypatch.setattr(apply, "reset_kde_color_scheme_config", lambda s: True)
    monkeypatch.setattr(apply, "_apply_lookandfeel_live", lambda laf: True)
    monkeypatch.setattr(apply, "cycle_widget_style_live", lambda style: True)
    monkeypatch.setattr(apply, "qdbus_cmd", lambda: None)

    apply.uninstall()

    assert [str(changeicons), "breeze"] in calls
    assert ["plasma-apply-cursortheme", "breeze_cursors"] in calls
    assert not any("Icons" in write or "cursorTheme" in write
                   for write in writes)


def test_uninstall_keeps_config_writes_as_official_tool_fallback(
        monkeypatch, tmp_path):
    writes: list = []
    oks, warns = _seed_uninstall_env(monkeypatch, tmp_path)
    monkeypatch.setattr(
        apply, "have",
        lambda cmd: cmd in {"kwriteconfig6", "plasma-apply-cursortheme"},
    )
    monkeypatch.setattr(
        apply, "feat_enabled",
        lambda name, default=True: name == "CURSORS",
    )
    monkeypatch.setattr(apply, "_live_plasma_ready_quick", lambda: True)
    monkeypatch.setattr(apply, "kde_libexec_binary",
                        lambda name: Path("/usr/lib/plasma-changeicons"))
    monkeypatch.setattr(apply, "_run_live", lambda command: False)
    monkeypatch.setattr(
        apply, "kw_write",
        lambda *args, **kwargs: writes.append(args) or True,
    )
    monkeypatch.setattr(apply, "reset_kde_color_scheme_config",
                        lambda scheme: True)

    apply.uninstall()

    assert any("cursorTheme" in write and "breeze_cursors" in write
               for write in writes)
    assert any("Icons" in write and "breeze" in write for write in writes)
    assert "Cursor reset" in oks
    assert "Icons reset" in oks
    assert not any("Cursor reset failed" in message
                   or "Icons reset failed" in message for message in warns)


def test_uninstall_wallpaper_failure_warns_instead_of_ok(monkeypatch,
                                                          tmp_path):
    wallpaper = tmp_path / "Next"
    wallpaper.mkdir()
    oks, warns = _seed_uninstall_env(monkeypatch, tmp_path)
    monkeypatch.setattr(apply, "_BREEZE_WALLPAPER", wallpaper)
    monkeypatch.setattr(
        apply, "have",
        lambda cmd: cmd in {"kwriteconfig6", "plasma-apply-wallpaperimage"},
    )
    monkeypatch.setattr(
        apply, "feat_enabled",
        lambda name, default=True: name == "WALLPAPERS",
    )
    monkeypatch.setattr(apply, "_live_plasma_ready_quick", lambda: True)
    monkeypatch.setattr(apply, "_run_live", lambda cmd: False)
    monkeypatch.setattr(apply, "reset_kde_color_scheme_config", lambda s: True)

    apply.uninstall()

    assert "Wallpaper reset" not in oks
    assert any("Wallpaper reset failed" in message for message in warns)


def test_uninstall_wallpaper_uses_disk_fallback_when_live_apply_fails(
        monkeypatch, tmp_path):
    wallpaper = tmp_path / "Next"
    wallpaper.mkdir()
    oks, warns = _seed_uninstall_env(monkeypatch, tmp_path)
    current = [{"screen": 0, "image": "file:///old.jpg"}]
    snapshots = []
    monkeypatch.setattr(apply, "_BREEZE_WALLPAPER", wallpaper)
    monkeypatch.setattr(
        apply, "have",
        lambda cmd: cmd in {"kwriteconfig6", "plasma-apply-wallpaperimage"},
    )
    monkeypatch.setattr(apply, "feat_enabled",
                        lambda name, default=True: name == "WALLPAPERS")
    monkeypatch.setattr(apply, "_live_plasma_ready_quick", lambda: True)
    monkeypatch.setattr(apply, "_run_live", lambda cmd: False)
    monkeypatch.setattr(apply, "_current_wallpapers", lambda: current)
    monkeypatch.setattr(
        apply, "_apply_wallpaper_snapshot",
        lambda snapshot: snapshots.append(snapshot) or True,
    )
    monkeypatch.setattr(apply, "reset_kde_color_scheme_config", lambda s: True)

    apply.uninstall()

    assert snapshots == [[{"screen": 0, "image": f"file://{wallpaper}"}]]
    assert "Wallpaper reset" in oks
    assert not any("Wallpaper reset" in message for message in warns)


def test_uninstall_wallpaper_headless_writes_config_without_live_dbus(
        monkeypatch, tmp_path):
    wallpaper = tmp_path / "Next"
    wallpaper.mkdir()
    oks, warns = _seed_uninstall_env(monkeypatch, tmp_path)
    written = []
    monkeypatch.setattr(apply, "_BREEZE_WALLPAPER", wallpaper)
    monkeypatch.setattr(apply, "feat_enabled",
                        lambda name, default=True: name == "WALLPAPERS")
    monkeypatch.setattr(apply, "_wallpapers_from_config", lambda: [])
    monkeypatch.setattr(
        apply, "_write_wallpapers_to_config",
        lambda snapshot: written.append(snapshot) or True,
    )
    monkeypatch.setattr(
        apply, "_current_wallpapers",
        lambda: (_ for _ in ()).throw(AssertionError("live DBus capture used")),
    )
    monkeypatch.setattr(
        apply, "_apply_wallpaper_snapshot",
        lambda snapshot: (_ for _ in ()).throw(AssertionError("live apply used")),
    )
    monkeypatch.setattr(apply, "reset_kde_color_scheme_config", lambda s: True)

    apply.uninstall()

    assert written == [[{"screen": 0, "image": f"file://{wallpaper}"}]]
    assert "Wallpaper reset" in oks
    assert not any("Wallpaper reset" in message for message in warns)


def test_uninstall_wallpaper_missing_tool_warns_instead_of_ok(
        monkeypatch, tmp_path):
    wallpaper = tmp_path / "Next"
    wallpaper.mkdir()
    oks, warns = _seed_uninstall_env(monkeypatch, tmp_path)
    monkeypatch.setattr(apply, "_BREEZE_WALLPAPER", wallpaper)
    monkeypatch.setattr(apply, "feat_enabled",
                        lambda name, default=True: name == "WALLPAPERS")
    monkeypatch.setattr(apply, "reset_kde_color_scheme_config",
                        lambda scheme: True)

    apply.uninstall()

    assert "Wallpaper reset" not in oks
    assert any("live helper not found" in message
               for message in warns)


def test_uninstall_wallpaper_has_no_fake_fallback_directories():
    source = Path(apply.__file__).read_text()
    assert "/usr/share/wallpapers/Breeze" not in source
    assert "/usr/share/wallpapers/Flow" not in source
