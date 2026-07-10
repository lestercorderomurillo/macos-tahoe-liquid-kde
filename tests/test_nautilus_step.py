"""Nautilus sidebar bookmarks (v0.24.x).

``nautilus._apply_overrides()`` writes ``~/.config/gtk-3.0/bookmarks``
from the bundled ``src/offline/nautilus/bookmarks`` template. The
template uses a ``$HOME`` token so the same file works for any user;
the step must substitute the current user's home before writing.
"""

from __future__ import annotations

from pathlib import Path


def _run_apply_overrides(tmp_path, monkeypatch, template_text=None):
    """Wire nautilus.py to a fake home + fake offline tree, then run
    ``_apply_overrides()``. Returns the written bookmarks path."""
    from steps import nautilus

    home = tmp_path / "home"
    home.mkdir()

    offline_nautilus = tmp_path / "offline" / "nautilus"
    offline_nautilus.mkdir(parents=True)
    if template_text is not None:
        (offline_nautilus / "bookmarks").write_text(
            template_text, encoding="utf-8"
        )

    monkeypatch.setattr(nautilus, "HOME", home)
    monkeypatch.setattr(nautilus, "offline", lambda *_a: offline_nautilus)

    # The gtk.css branch also runs in _apply_overrides; keep it
    # from touching the real tree / complaining.
    monkeypatch.setattr(nautilus, "ok", lambda _msg: None)
    monkeypatch.setattr(nautilus, "warn", lambda _msg: None)
    monkeypatch.setattr(nautilus, "fail", lambda _msg: None)

    nautilus._apply_overrides()

    return home / ".config" / "gtk-3.0" / "bookmarks"


def test_bookmarks_substitutes_home(tmp_path, monkeypatch):
    """The ``$HOME`` token in the template must be rewritten to the
    real home path so the sidebar points at the current user's
    folders instead of a path baked into the repo."""
    bookmarks = _run_apply_overrides(
        tmp_path,
        monkeypatch,
        template_text=(
            "file://$HOME/Documentos Documentos\n"
            "file://$HOME/Downloads Downloads\n"
            "file://$HOME/%C3%81rea%20de%20trabalho Área de trabalho\n"
        ),
    )

    assert bookmarks.is_file(), "bookmarks file was not written"
    content = bookmarks.read_text(encoding="utf-8")
    assert "$HOME" not in content, "literal $HOME token leaked into output"
    assert "file://" + str(tmp_path / "home") + "/Documentos" in content
    assert "file://" + str(tmp_path / "home") + "/Downloads" in content
    assert "Área de trabalho" in content


def test_bookmarks_missing_template_is_silent(tmp_path, monkeypatch):
    """When the bundled template is absent (the original bug), the
    step must not crash and must not write a stale/empty bookmarks
    file. (The missing-template gap is a packaging bug, not a runtime
    one -- covered by shipping the file, not by this guard.)"""
    bookmarks = _run_apply_overrides(tmp_path, monkeypatch, template_text=None)
    assert not bookmarks.exists()
