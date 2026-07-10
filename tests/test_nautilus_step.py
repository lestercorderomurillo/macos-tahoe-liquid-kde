"""Nautilus sidebar bookmarks (v0.24.x).

``nautilus._generate_bookmarks()`` writes ``~/.config/gtk-3.0/bookmarks``
from ``~/.config/user-dirs.dirs`` so the labels follow the system
language (Desktop, Documentos, Download, …) instead of a hardcoded
template.
"""

from __future__ import annotations

from pathlib import Path


def _run_generate_bookmarks(
    tmp_path, monkeypatch, user_dirs_text
) -> Path:
    """Wire nautilus.py to a fake home with a user-dirs.dirs and real
    XDG directories, then run ``_generate_bookmarks()``. Returns the
    written bookmarks path."""
    from steps import nautilus

    home = tmp_path / "home"
    home.mkdir()

    # Write user-dirs.dirs
    (home / ".config").mkdir(parents=True)
    (home / ".config/user-dirs.dirs").write_text(
        user_dirs_text, encoding="utf-8"
    )

    # Create the actual XDG directories so path.is_dir() passes
    for line in user_dirs_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if 'XDG_' in line and '_DIR="' in line:
            import re
            m = re.match(r'^XDG_\w+_DIR="(.+)"$', line)
            if m:
                path_str = m.group(1).replace("$HOME", str(home))
                Path(path_str).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(nautilus, "HOME", home)
    monkeypatch.setattr(nautilus, "ok", lambda _msg: None)
    monkeypatch.setattr(nautilus, "warn", lambda _msg: None)
    monkeypatch.setattr(nautilus, "fail", lambda _msg: None)

    nautilus._generate_bookmarks()

    return home / ".config" / "gtk-3.0" / "bookmarks"


def test_bookmarks_generated_from_xdg_user_dirs_pt(tmp_path, monkeypatch):
    """Portuguese locale: labels match the XDG dir names on disk."""
    bookmarks = _run_generate_bookmarks(
        tmp_path,
        monkeypatch,
        user_dirs_text=(
            '# Portuguese locale\n'
            'XDG_DESKTOP_DIR="$HOME/Área de trabalho"\n'
            'XDG_DOCUMENTS_DIR="$HOME/Documentos"\n'
            'XDG_DOWNLOAD_DIR="$HOME/Downloads"\n'
            'XDG_PICTURES_DIR="$HOME/Imagens"\n'
            'XDG_VIDEOS_DIR="$HOME/Vídeos"\n'
            'XDG_MUSIC_DIR="$HOME/Músicas"\n'
        ),
    )

    assert bookmarks.is_file(), "bookmarks file was not written"
    content = bookmarks.read_text(encoding="utf-8")
    assert "Área de trabalho" in content
    assert "Imagens" in content


def test_bookmarks_generated_from_xdg_user_dirs_en(tmp_path, monkeypatch):
    """English locale: labels match the XDG dir names on disk."""
    bookmarks = _run_generate_bookmarks(
        tmp_path,
        monkeypatch,
        user_dirs_text=(
            'XDG_DESKTOP_DIR="$HOME/Desktop"\n'
            'XDG_DOCUMENTS_DIR="$HOME/Documents"\n'
            'XDG_DOWNLOAD_DIR="$HOME/Downloads"\n'
            'XDG_PICTURES_DIR="$HOME/Pictures"\n'
            'XDG_VIDEOS_DIR="$HOME/Videos"\n'
            'XDG_MUSIC_DIR="$HOME/Music"\n'
        ),
    )

    content = bookmarks.read_text(encoding="utf-8")
    assert "Desktop" in content
    assert "Documents" in content
    assert "Music" in content
    assert "Pictures" in content


def test_bookmarks_missing_user_dirs_is_silent(tmp_path, monkeypatch):
    """When ~/.config/user-dirs.dirs does not exist, no bookmarks file
    should be written and no crash should occur."""
    from steps import nautilus

    home = tmp_path / "home"
    home.mkdir()

    monkeypatch.setattr(nautilus, "HOME", home)
    monkeypatch.setattr(nautilus, "ok", lambda _msg: None)
    monkeypatch.setattr(nautilus, "warn", lambda _msg: None)
    monkeypatch.setattr(nautilus, "fail", lambda _msg: None)

    nautilus._generate_bookmarks()

    bookmarks = home / ".config" / "gtk-3.0" / "bookmarks"
    assert not bookmarks.exists()


def test_bookmarks_order_follows_xdg_sidebar_order(tmp_path, monkeypatch):
    """The order of entries in the bookmarks file must match
    _XDG_SIDEBAR_ORDER, not the order in user-dirs.dirs."""
    bookmarks = _run_generate_bookmarks(
        tmp_path,
        monkeypatch,
        user_dirs_text=(
            'XDG_MUSIC_DIR="$HOME/Music"\n'
            'XDG_DOWNLOAD_DIR="$HOME/Downloads"\n'
            'XDG_DESKTOP_DIR="$HOME/Desktop"\n'
            'XDG_PICTURES_DIR="$HOME/Pictures"\n'
            'XDG_VIDEOS_DIR="$HOME/Videos"\n'
            'XDG_DOCUMENTS_DIR="$HOME/Documents"\n'
        ),
    )

    lines = bookmarks.read_text(encoding="utf-8").strip().splitlines()
    # Should be: DESKTOP, DOCUMENTS, DOWNLOAD, PICTURES, VIDEOS, MUSIC
    labels = [line.split()[-1] for line in lines]
    assert labels == ["Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music"], (
        f"Expected fixed order, got: {labels}"
    )
