"""Portability + hang-safety tests for the apply step: the live
KWin-reconfigure guard resolves qdbus via utils.qdbus_cmd() (Fedora's
qdbus-qt6), and _run_live bounds its calls with a timeout.
"""

import subprocess

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

    # Must return None without raising.
    assert apply._run_live(["plasma-apply-wallpaperimage", "/x"]) is None


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
