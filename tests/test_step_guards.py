"""Step-level dependency guards (v0.15.5).

Every step that calls out to a tool we don't ship (``kwriteconfig6``,
``fc-cache``, ``grub-mkconfig``, ...) must explicitly check the tool
exists and surface a clear ``warn()`` when it doesn't — instead of
the silent-success-but-half-applied state the installer used to land
in on minimal systemd+KDE installs where one of those binaries is
missing.

These tests stub the tool's presence + the helpers and assert the
expected warn() message fires. They do not run the full install
pipeline — that's covered by tests/test_plymouth_step.py etc.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# steps live under src/scripts; conftest already wires the import path
# via the repo / src fixtures used elsewhere.


# ── kvantum.py: kw_write failure warning ─────────────────────────────


def test_kvantum_warns_when_kwriteconfig6_missing(tmp_path, monkeypatch):
    """kvantum.install() copies the theme files (filesystem only —
    those always work) then writes ``widgetStyle=kvantum`` to
    kdeglobals. If kwriteconfig6 isn't installed, ``kw_write()``
    returns False; the step used to silently skip the ``ok()``
    confirmation, leaving the user wondering why Kvantum 'isn't
    working'. Now it must surface an actionable warn()."""
    from steps import kvantum

    # Point kvantum at an offline source it can read.
    fake_src = tmp_path / "fake-offline" / "kvantum/mac-tahoe-liquid-kde"
    fake_src.mkdir(parents=True)
    (fake_src / "mac-tahoe-liquid-kde.kvconfig").write_text("[General]\n")
    (fake_src / "mac-tahoe-liquid-kde.svg").write_text("<svg/>")
    # kvantum.py now installs both light and dark themes
    (fake_src / "mac-tahoe-liquid-kdeDark.kvconfig").write_text("[General]\n")
    (fake_src / "mac-tahoe-liquid-kdeDark.svg").write_text("<svg/>")

    dest = tmp_path / "home/.config/Kvantum/mac-tahoe-liquid-kde"
    dest_dark = tmp_path / "home/.config/Kvantum/mac-tahoe-liquid-kdeDark"
    monkeypatch.setattr(kvantum, "DEST_DIR", dest)
    monkeypatch.setattr(kvantum, "DEST_DIR_DARK", dest_dark)
    monkeypatch.setattr(kvantum, "offline", lambda *_a: fake_src)

    # kwriteconfig6 missing → kw_write returns False.
    monkeypatch.setattr(kvantum, "kw_write", lambda *_a, **_kw: False)

    warnings: list[str] = []
    monkeypatch.setattr(kvantum, "warn", warnings.append)
    monkeypatch.setattr(kvantum, "ok", lambda _msg: None)
    monkeypatch.setattr(kvantum, "reinstall", lambda _msg: None)
    monkeypatch.setattr(kvantum, "fail", lambda _msg: None)

    kvantum.install()

    assert any("kwriteconfig6" in w for w in warnings), (
        f"expected a warn() mentioning kwriteconfig6, got: {warnings}"
    )


def test_kvantum_does_not_warn_when_kwriteconfig6_present(tmp_path, monkeypatch):
    """Positive control: when kw_write succeeds, no spurious warn()
    about kwriteconfig6 — the success path stays clean."""
    from steps import kvantum

    fake_src = tmp_path / "fake-offline" / "kvantum/mac-tahoe-liquid-kde"
    fake_src.mkdir(parents=True)
    (fake_src / "mac-tahoe-liquid-kde.kvconfig").write_text("[General]\n")
    (fake_src / "mac-tahoe-liquid-kdeDark.kvconfig").write_text("[General]\n")
    (fake_src / "mac-tahoe-liquid-kdeDark.svg").write_text("<svg/>")

    dest = tmp_path / "home/.config/Kvantum/mac-tahoe-liquid-kde"
    dest_dark = tmp_path / "home/.config/Kvantum/mac-tahoe-liquid-kdeDark"
    monkeypatch.setattr(kvantum, "DEST_DIR", dest)
    monkeypatch.setattr(kvantum, "DEST_DIR_DARK", dest_dark)
    monkeypatch.setattr(kvantum, "offline", lambda *_a: fake_src)
    monkeypatch.setattr(kvantum, "kw_write", lambda *_a, **_kw: True)

    warnings: list[str] = []
    monkeypatch.setattr(kvantum, "warn", warnings.append)
    monkeypatch.setattr(kvantum, "ok", lambda _msg: None)
    monkeypatch.setattr(kvantum, "reinstall", lambda _msg: None)
    monkeypatch.setattr(kvantum, "fail", lambda _msg: None)

    kvantum.install()

    assert not any("kwriteconfig6" in w for w in warnings), (
        f"unexpected kwriteconfig6 warning on success path: {warnings}"
    )


# ── window_decorations.py: kw_write failure warning ─────────────────


def test_window_decorations_warns_when_kwinrc_writes_fail(tmp_path, monkeypatch):
    """Aurorae files install via plain filesystem copies (those
    always work), but the kwinrc keys that select our theme are
    written via kwriteconfig6. If those writes fail (kwriteconfig6
    missing), the user gets the theme files on disk but Plasma keeps
    using Breeze decorations on next login. The step must warn
    explicitly instead of pretending everything worked."""
    from steps import window_decorations as wd

    # Build a minimal fake offline tree so install() can iterate.
    fake_src = tmp_path / "fake-offline" / "aurorae"
    for variant in ("Dark", "Light"):
        d = fake_src / f"MacTahoeLiquidKde-{variant}"
        d.mkdir(parents=True)

    dest = tmp_path / "home/.local/share/aurorae/themes"
    monkeypatch.setattr(wd, "DEST_DIR", dest)
    monkeypatch.setattr(wd, "offline", lambda *_a: fake_src)

    # Every kw_write fails — simulates a missing kwriteconfig6 binary.
    monkeypatch.setattr(wd, "kw_write", lambda *_a, **_kw: False)
    monkeypatch.setattr(wd, "qdbus_call", lambda *_a, **_kw: True)
    monkeypatch.setattr(wd, "theme_mode", lambda: "dark")

    warnings: list[str] = []
    monkeypatch.setattr(wd, "warn", warnings.append)
    monkeypatch.setattr(wd, "ok", lambda _msg: None)
    monkeypatch.setattr(wd, "reinstall", lambda _msg: None)
    monkeypatch.setattr(wd, "info", lambda _msg: None)
    monkeypatch.setattr(wd, "fail", lambda _msg: None)

    wd.install()

    assert any("kwriteconfig6" in w for w in warnings), (
        f"expected warn() mentioning kwriteconfig6, got: {warnings}"
    )


def test_window_decorations_clean_ok_when_writes_succeed(tmp_path, monkeypatch):
    """Positive control: on the happy path the ok() message
    ``Window decoration set to MacTahoeLiquidKde-Dark`` fires and no
    kwriteconfig6 warning appears."""
    from steps import window_decorations as wd

    fake_src = tmp_path / "fake-offline" / "aurorae"
    for variant in ("Dark", "Light"):
        (fake_src / f"MacTahoeLiquidKde-{variant}").mkdir(parents=True)

    dest = tmp_path / "home/.local/share/aurorae/themes"
    monkeypatch.setattr(wd, "DEST_DIR", dest)
    monkeypatch.setattr(wd, "offline", lambda *_a: fake_src)
    monkeypatch.setattr(wd, "kw_write", lambda *_a, **_kw: True)
    monkeypatch.setattr(wd, "qdbus_call", lambda *_a, **_kw: True)
    monkeypatch.setattr(wd, "theme_mode", lambda: "dark")

    oks: list[str] = []
    warnings: list[str] = []
    monkeypatch.setattr(wd, "warn", warnings.append)
    monkeypatch.setattr(wd, "ok", oks.append)
    monkeypatch.setattr(wd, "reinstall", lambda _msg: None)
    monkeypatch.setattr(wd, "info", lambda _msg: None)
    monkeypatch.setattr(wd, "fail", lambda _msg: None)

    wd.install()

    assert any("Window decoration set to MacTahoeLiquidKde-Dark" in m
               for m in oks), oks
    assert not any("kwriteconfig6" in w for w in warnings), warnings


# ── plasma_theme.py: uninstall kw_write failure warning ─────────────


def test_plasma_theme_uninstall_warns_when_reset_write_fails(tmp_path, monkeypatch):
    """plasma_theme.uninstall() resets ``plasmarc:Theme.name`` to
    ``default`` so Plasma falls back cleanly. If kwriteconfig6 is
    missing, the file removal still happens but the active-theme
    pointer stays on our (now-deleted) name — Plasma errors on next
    login. The user must be told."""
    from steps import plasma_theme

    monkeypatch.setattr(plasma_theme, "remove_tree", lambda *_a, **_kw: True)
    monkeypatch.setattr(plasma_theme, "kw_write", lambda *_a, **_kw: False)

    warnings: list[str] = []
    monkeypatch.setattr(plasma_theme, "warn", warnings.append)
    monkeypatch.setattr(plasma_theme, "info", lambda _msg: None)

    plasma_theme.uninstall()

    assert any("kwriteconfig6" in w for w in warnings), warnings


# ── fonts.py: fc-cache guard ────────────────────────────────────────


def test_fonts_warns_when_fc_cache_missing(tmp_path, monkeypatch):
    """fc-cache lives in the ``fontconfig`` package, which isn't
    *technically* mandatory on a minimal Plasma install — some
    embedded / atomic builds strip it. Without it the .otf/.ttf
    files copy fine but Qt apps still see the old font list until
    logout. Surface the gap explicitly."""
    from steps import fonts

    # have() returns False → fc-cache treated as missing.
    monkeypatch.setattr(fonts, "have", lambda _c: False)
    warnings: list[str] = []
    monkeypatch.setattr(fonts, "warn", warnings.append)

    runs: list[list[str]] = []

    def fake_run_user(argv, **kwargs):
        runs.append(list(argv))
        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(fonts, "run_user", fake_run_user)

    fonts._refresh_font_cache()

    assert runs == [], (
        f"fc-cache was invoked even though have() returned False: {runs}"
    )
    assert any("fc-cache" in w for w in warnings), warnings


def test_fonts_runs_fc_cache_when_present(tmp_path, monkeypatch):
    """Positive control: when have('fc-cache') is True, the cache
    refresh subprocess actually runs and no warn() fires."""
    from steps import fonts

    monkeypatch.setattr(fonts, "have", lambda _c: True)
    warnings: list[str] = []
    monkeypatch.setattr(fonts, "warn", warnings.append)

    runs: list[list[str]] = []

    def fake_run_user(argv, **kwargs):
        runs.append(list(argv))
        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(fonts, "run_user", fake_run_user)

    fonts._refresh_font_cache()

    assert runs, "fc-cache was not invoked even though have() returned True"
    assert "fc-cache" in runs[0][0]
    assert not any("fc-cache not found" in w for w in warnings), warnings
