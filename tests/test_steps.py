# USELESS: sandboxed step install/uninstall under tmp_path — production destinations differ and are unloadable by Plasma
"""Sandboxed install/uninstall behaviour for individual step modules."""

import os
import subprocess
from pathlib import Path

import pytest

from .conftest import has_command


def _run(step: str, phase: str, env: dict[str, str] | None = None) -> int:
    full = os.environ.copy()
    full.setdefault("MAC_TAHOE_SKIP_LIVE_APPLY", "true")
    if env:
        full.update(env)
    return subprocess.run(
        ["python3", "-c",
         f"from steps.{step} import {phase}; {phase}()"],
        check=False, env=full,
        cwd=str(Path(__file__).resolve().parent.parent / "src/scripts"),
    ).returncode


def _journal_matches(pattern: str, since: str = "24 hours ago") -> list[str]:
    res = subprocess.run(
        ["journalctl", "--user", "-p", "err", "--since", since, "--no-pager"],
        check=False,
        capture_output=True,
        text=True,
    )
    import re

    bad = re.compile(pattern, re.IGNORECASE)
    return [line for line in res.stdout.splitlines() if bad.search(line)]


# ── color schemes ────────────────────────────────────────────────────────
def test_color_schemes_install_uninstall_cycle(sandbox):
    css_dir = sandbox / ".local/share/color-schemes"

    assert _run("color_schemes", "install") == 0
    assert (css_dir / "MacTahoeLiquidKdeLight.colors").is_file()
    assert (css_dir / "MacTahoeLiquidKdeDark.colors").is_file()

    assert _run("color_schemes", "uninstall") == 0
    assert not (css_dir / "MacTahoeLiquidKdeLight.colors").exists()
    assert not (css_dir / "MacTahoeLiquidKdeDark.colors").exists()

    assert _run("color_schemes", "install") == 0
    assert (css_dir / "MacTahoeLiquidKdeLight.colors").is_file()

    # Double install / uninstall must not error.
    assert _run("color_schemes", "install") == 0
    assert _run("color_schemes", "uninstall") == 0
    assert _run("color_schemes", "uninstall") == 0


@pytest.mark.parametrize("iteration", [1, 2, 3])
def test_color_schemes_loop(sandbox, iteration):
    assert _run("color_schemes", "install") == 0
    assert (sandbox / ".local/share/color-schemes/MacTahoeLiquidKdeDark.colors").is_file()
    assert _run("color_schemes", "uninstall") == 0
    assert not (sandbox / ".local/share/color-schemes/MacTahoeLiquidKdeDark.colors").exists()


# ── nautilus ─────────────────────────────────────────────────────────────
def test_safe_copy_stages_outside_destination_directory(monkeypatch, tmp_path):
    """plasmashell's KDirWatch lives on ``~/.local/share/wallpapers``. If
    ``safe_copy`` writes its ``.tmp_*`` / ``.bak_*`` siblings inside that
    dir, plasmashell scans them as half-built wallpaper packages and has
    been observed crashing inside ``libplasma_wallpaper_image.so``.
    Staging must happen elsewhere — verify by checking that no temp
    artefacts ever appear next to the destination during the copy."""
    import utils

    # Lazy ``_staging_root()`` reads XDG_CACHE_HOME on every call, so
    # setting the env var is enough — no module-level monkeypatch needed.
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    src = tmp_path / "src/MyPkg"
    (src / "contents").mkdir(parents=True)
    (src / "contents/file.txt").write_text("hi")
    (src / "metadata.json").write_text("{}")

    dest_parent = tmp_path / "dest"
    dest = dest_parent / "MyPkg"

    assert utils.safe_copy(src, dest) is True

    siblings = [p.name for p in dest_parent.iterdir()]
    assert siblings == ["MyPkg"], (
        f"safe_copy left artefacts inside the destination dir: {siblings} — "
        "those would be scanned by plasmashell's KDirWatch and could trip "
        "the libplasma_wallpaper_image crash."
    )

    # Staging root MUST live outside dest_parent — that's the whole
    # reason we route through XDG_CACHE_HOME instead of dest's sibling.
    staging_root = utils._staging_root()
    assert not str(staging_root).startswith(str(dest_parent)), (
        "staging root is nested inside the destination tree — that defeats "
        "the whole point of staging outside KDirWatch's view."
    )

    # Final state on disk must be a complete copy of src, not a partial.
    assert (dest / "metadata.json").read_text() == "{}"
    assert (dest / "contents/file.txt").read_text() == "hi"


def test_install_bundled_wallpaper_lands_in_dest(monkeypatch, tmp_path):
    """v0.17: wallpapers are 100% offline. install() copies every
    ``Mac*/`` directory under ``src/offline/wallpapers/`` straight into
    ``~/.local/share/wallpapers/``. No download, no cache, no
    network."""
    from steps import wallpapers

    home = tmp_path / "home"
    offline = tmp_path / "offline"
    dest = home / ".local/share/wallpapers"

    bundled = offline / "MacTahoe-Bundled-Test"
    (bundled / "contents/images").mkdir(parents=True, exist_ok=True)
    (bundled / "contents/images/3840x2160.jpg").write_bytes(b"FAKE_JPEG")
    (bundled / "metadata.json").write_text(
        '{"KPlugin": {"Id": "MacTahoe-Bundled-Test"}}'
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(wallpapers, "HOME", home)
    monkeypatch.setattr(wallpapers, "DEST_DIR", dest)
    monkeypatch.setattr(wallpapers, "OFFLINE_DIR", offline)

    wallpapers.install()

    assert (dest / "MacTahoe-Bundled-Test/metadata.json").is_file()
    assert (dest / "MacTahoe-Bundled-Test/contents/images/3840x2160.jpg").read_bytes() == b"FAKE_JPEG"


def test_install_skips_bundle_with_no_metadata(monkeypatch, tmp_path):
    """A Mac*/ dir without metadata.json is a half-finished commit (e.g.
    someone added images but forgot the json). install() must skip it
    with a clear fail() instead of landing a wallpaper Plasma can't
    list."""
    from steps import wallpapers

    home = tmp_path / "home"
    offline = tmp_path / "offline"
    dest = home / ".local/share/wallpapers"

    broken = offline / "MacTahoe-Broken"
    (broken / "contents/images").mkdir(parents=True, exist_ok=True)
    (broken / "contents/images/3840x2160.jpg").write_bytes(b"x")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(wallpapers, "HOME", home)
    monkeypatch.setattr(wallpapers, "DEST_DIR", dest)
    monkeypatch.setattr(wallpapers, "OFFLINE_DIR", offline)

    failures: list[str] = []
    monkeypatch.setattr(wallpapers, "fail", lambda m: failures.append(m))
    monkeypatch.setattr(wallpapers, "info", lambda _m: None)

    wallpapers.install()

    assert not (dest / "MacTahoe-Broken").exists()
    assert any("metadata.json" in m for m in failures), failures


def test_install_picks_up_iridescence_from_repo_offline_dir(monkeypatch, tmp_path, repo):
    """End-to-end check against the REAL repo offline tree — guards
    against the bundled MacTahoe-Iridescence (or any future Mac*/ pack)
    silently disappearing."""
    from steps import wallpapers

    home = tmp_path / "home"
    dest = home / ".local/share/wallpapers"

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(wallpapers, "HOME", home)
    monkeypatch.setattr(wallpapers, "DEST_DIR", dest)
    monkeypatch.setattr(wallpapers, "OFFLINE_DIR", repo / "src/offline/wallpapers")

    wallpapers.install()

    assert (dest / "MacTahoe-Iridescence/metadata.json").is_file()
    assert (dest / "MacTahoe-Iridescence/contents/images").is_dir()


def test_repo_ships_full_macos_wallpaper_set(repo):
    """v0.17 contract: the install no longer downloads from
    512pixels.net. Every wallpaper the README claims must therefore
    be present in src/offline/wallpapers/ at commit time, with both a
    metadata.json and at least one image file under contents/. If
    someone adds a new entry to _FIXED_NAMES but forgets the bundle,
    or vice versa, this test catches it."""
    from steps import wallpapers as wp_mod
    offline_dir = repo / "src/offline/wallpapers"
    for name in wp_mod._FIXED_NAMES:
        bundle = offline_dir / name
        assert bundle.is_dir(), f"{name} listed in _FIXED_NAMES but not bundled at {bundle}"
        assert (bundle / "metadata.json").is_file(), f"{name} missing metadata.json"
        images = list((bundle / "contents").rglob("3840x2160.*"))
        assert images, f"{name} has no 3840x2160 image under contents/"


def test_nautilus_no_fatal(sandbox, monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    (sandbox / ".config/gtk-3.0").mkdir(parents=True, exist_ok=True)
    rc = _run("nautilus", "install", {"XDG_CURRENT_DESKTOP": "KDE"})
    assert rc == 0
    rc = _run("nautilus", "uninstall", {"XDG_CURRENT_DESKTOP": "KDE"})
    assert rc == 0


# ── crash / regression guards ────────────────────────────────────────────
def test_no_globalmenu_crashes_in_journal():
    if not has_command("journalctl"):
        pytest.skip("journalctl unavailable")
    matches = _journal_matches(
        r"(org\.kde\.mac\.tahoe\.liquid\.(globalmenu|menu))\.so.*"
        r"(segfault|coredump|terminated|aborted)"
    )
    assert not matches, "\n".join(matches[:5])


def test_no_taskmanager_badge_crashes_in_journal():
    if not has_command("journalctl"):
        pytest.skip("journalctl unavailable")
    matches = _journal_matches(
        r"((org\.kde\.mac\.tahoe\.liquid\.taskmanager(\.so)?)|"
        r"TaskBadgeOverlay\.qml|BadgeEffect).*"
        r"(segfault|coredump|terminated|aborted|crash)"
    )
    assert not matches, "\n".join(matches[:5])


def test_no_plasma_crashes_in_journal():
    if not has_command("journalctl"):
        pytest.skip("journalctl unavailable")
    matches = _journal_matches(
        r"((plasmashell|plasma-plasmashell|org\.kde\.plasma).*)"
        r"(segfault|coredump|terminated|aborted|crash)"
    )
    assert not matches, "\n".join(matches[:5])


def test_no_nautilus_crashes_in_journal():
    if not has_command("journalctl"):
        pytest.skip("journalctl unavailable")
    matches = _journal_matches(
        r"((nautilus|org\.gnome\.Nautilus).*)"
        r"(segfault|coredump|terminated|aborted|crash)"
    )
    assert not matches, "\n".join(matches[:5])
