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
