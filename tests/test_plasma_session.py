"""Regression tests for the single Plasma-session detector.

Step 2 (``verify_plasma``) and the Nautilus step used to answer "is this
KDE Plasma?" with two unrelated mechanisms: the preflight gate probed the
``plasmashell`` binary, while ``nautilus._is_kde`` read session env vars
*alone*. ``sudo`` strips that environment, so on a real ``sudo ./install``
the Nautilus step reported "Not running under KDE Plasma" even though
preflight had just confirmed Plasma from the binary.

The fix collapses both onto ``utils.is_plasma_session()``, which anchors
on the sudo-proof binary and treats the env vars only as a corroborating
positive. These tests pin that contract:

  * binary present  → Plasma, even with the whole session env stripped
    (the exact sudo regression);
  * binary absent + a session env var set → still Plasma;
  * binary absent + empty env → not Plasma;
  * the Nautilus step delegates to the shared helper rather than
    re-deriving the answer from the environment.
"""

import importlib

import utils


_SESSION_VARS = (
    "XDG_CURRENT_DESKTOP",
    "XDG_SESSION_DESKTOP",
    "KDE_FULL_SESSION",
    "KDE_SESSION_VERSION",
)


def _strip_session_env(monkeypatch) -> None:
    """Reproduce what ``sudo`` does to the graphical session env."""
    for var in _SESSION_VARS:
        monkeypatch.delenv(var, raising=False)


def test_binary_present_is_plasma_even_with_env_stripped(monkeypatch):
    # The sudo regression: preflight saw plasmashell, but the Nautilus
    # step's env-only check came back empty and said "not Plasma".
    monkeypatch.setattr(utils, "have", lambda cmd: cmd == "plasmashell")
    _strip_session_env(monkeypatch)

    assert utils.is_plasma_session() is True


def test_binary_absent_but_session_env_present_is_plasma(monkeypatch):
    monkeypatch.setattr(utils, "have", lambda cmd: False)
    _strip_session_env(monkeypatch)
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")

    assert utils.is_plasma_session() is True


def test_xdg_current_desktop_matches_within_colon_list(monkeypatch):
    # XDG_CURRENT_DESKTOP is colon-separated (e.g. "KDE" or "X-Foo:KDE").
    monkeypatch.setattr(utils, "have", lambda cmd: False)
    _strip_session_env(monkeypatch)
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "X-Custom:KDE")

    assert utils.is_plasma_session() is True


def test_presence_only_env_var_counts(monkeypatch):
    # KDE_FULL_SESSION / KDE_SESSION_VERSION are presence flags, not
    # value-matched: any non-empty value means "Plasma".
    monkeypatch.setattr(utils, "have", lambda cmd: False)
    _strip_session_env(monkeypatch)
    monkeypatch.setenv("KDE_FULL_SESSION", "true")

    assert utils.is_plasma_session() is True


def test_binary_absent_and_empty_env_is_not_plasma(monkeypatch):
    monkeypatch.setattr(utils, "have", lambda cmd: False)
    _strip_session_env(monkeypatch)

    assert utils.is_plasma_session() is False


def test_foreign_desktop_value_is_not_plasma(monkeypatch):
    monkeypatch.setattr(utils, "have", lambda cmd: False)
    _strip_session_env(monkeypatch)
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    monkeypatch.setenv("XDG_SESSION_DESKTOP", "gnome")

    assert utils.is_plasma_session() is False


def test_nautilus_step_reuses_the_shared_helper(monkeypatch):
    # The Nautilus step must not keep a private detector. Forcing the
    # shared helper False makes install() skip with the warning; forcing
    # it True takes it past the guard. If the step re-derived the answer
    # from the environment, neither toggle would have any effect.
    import steps.nautilus as nautilus
    importlib.reload(nautilus)

    assert not hasattr(nautilus, "_is_kde")

    calls: list[str] = []
    monkeypatch.setattr(nautilus, "warn", lambda msg: calls.append(msg))
    monkeypatch.setattr(nautilus, "is_plasma_session", lambda: False)

    nautilus.install()

    assert calls and "Not running under KDE Plasma" in calls[0]


def test_helper_is_the_single_public_source(monkeypatch):
    # is_plasma_session lives in utils so both the CLI preflight and the
    # step modules import the one implementation.
    assert callable(utils.is_plasma_session)
