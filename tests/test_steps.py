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

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    # Force module-level re-evaluation of _STAGING_ROOT for this test.
    monkeypatch.setattr(utils, "_STAGING_ROOT",
                        Path(tmp_path / "cache" / "mac-tahoe-liquid-kde-staging"))

    src = tmp_path / "src/MyPkg"
    (src / "contents").mkdir(parents=True)
    (src / "contents/file.txt").write_text("hi")
    (src / "metadata.json").write_text("{}")

    dest_parent = tmp_path / "dest"
    dest = dest_parent / "MyPkg"

    # Snapshot dest_parent BEFORE copy so we can list intermediate state
    # by polling. We can't actually intercept mid-copy here, but we can
    # check post-copy that no .tmp_* / .bak_* litter survives.
    assert utils.safe_copy(src, dest) is True

    siblings = [p.name for p in dest_parent.iterdir()]
    assert siblings == ["MyPkg"], (
        f"safe_copy left artefacts inside the destination dir: {siblings} — "
        "those would be scanned by plasmashell's KDirWatch and could trip "
        "the libplasma_wallpaper_image crash."
    )

    # The staging dir is allowed to retain residue (cleanup is best-effort
    # and not security-relevant), but it MUST live outside dest_parent.
    staging_root = utils._STAGING_ROOT
    assert not str(staging_root).startswith(str(dest_parent)), (
        "staging root is nested inside the destination tree — that defeats "
        "the whole point of staging outside KDirWatch's view."
    )

    # Final state on disk must be a complete copy of src, not a partial.
    assert (dest / "metadata.json").read_text() == "{}"
    assert (dest / "contents/file.txt").read_text() == "hi"


def test_install_syncs_offline_wallpapers_without_download(monkeypatch, tmp_path):
    """A bundled wallpaper added in src/offline/wallpapers/ must land in
    the install destination even when download() is skipped by a cache
    shortcut. The 0.8.1 release shipped MacTahoe-Iridescence and the
    initial cut got it wrong: download() owned the offline → cache copy,
    so users with a populated cache from an earlier install never saw
    the new wallpaper."""
    from steps import wallpapers

    home = tmp_path / "home"
    cache = tmp_path / "cache"
    offline = tmp_path / "offline"
    dest = home / ".local/share/wallpapers"

    bundled = offline / "MacTahoe-Bundled-Test"
    (bundled / "contents/images").mkdir(parents=True, exist_ok=True)
    (bundled / "contents/images/3840x2160.jpg").write_bytes(b"FAKE_JPEG")
    (bundled / "metadata.json").write_text(
        '{"KPlugin": {"Id": "MacTahoe-Bundled-Test"}}'
    )

    # Pre-populate the cache as if download() had already run earlier
    # (the original triggering condition for the bug).
    pre_cached = cache / "MacTahoe"
    (pre_cached / "contents/images").mkdir(parents=True, exist_ok=True)
    (pre_cached / "contents/images/3840x2160.png").write_bytes(b"OLD")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(wallpapers, "HOME", home)
    monkeypatch.setattr(wallpapers, "CACHE", cache)
    monkeypatch.setattr(wallpapers, "LEGACY_CACHE", tmp_path / "legacy")
    monkeypatch.setattr(wallpapers, "DEST_DIR", dest)
    monkeypatch.setattr(wallpapers, "OFFLINE_DIR", offline)

    # Critically: do NOT call download(). install() must sync offline
    # wallpapers on its own — that's the contract.
    wallpapers.install()

    assert (dest / "MacTahoe-Bundled-Test/metadata.json").is_file()
    assert (dest / "MacTahoe-Bundled-Test/contents/images/3840x2160.jpg").read_bytes() == b"FAKE_JPEG"


def test_install_picks_up_iridescence_from_repo_offline_dir(monkeypatch, tmp_path, repo):
    """End-to-end check against the REAL repo offline tree — guards
    against the bundled MacTahoe-Iridescence (or any future Mac*/ pack)
    silently disappearing on a cache-hit install."""
    from steps import wallpapers

    home = tmp_path / "home"
    cache = tmp_path / "cache"
    dest = home / ".local/share/wallpapers"

    pre_cached = cache / "MacTahoe"
    (pre_cached / "contents/images").mkdir(parents=True, exist_ok=True)
    (pre_cached / "contents/images/3840x2160.png").write_bytes(b"OLD")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(wallpapers, "HOME", home)
    monkeypatch.setattr(wallpapers, "CACHE", cache)
    monkeypatch.setattr(wallpapers, "LEGACY_CACHE", tmp_path / "legacy")
    monkeypatch.setattr(wallpapers, "DEST_DIR", dest)
    monkeypatch.setattr(wallpapers, "OFFLINE_DIR", repo / "src/offline/wallpapers")

    wallpapers.install()

    assert (dest / "MacTahoe-Iridescence/metadata.json").is_file()
    assert (dest / "MacTahoe-Iridescence/contents/images").is_dir()


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
