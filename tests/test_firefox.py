from __future__ import annotations

import json
from pathlib import Path

import pytest

from steps import firefox


def _seed_profile(root: Path, name: str = "abc.default-release") -> Path:
    profile = root / name
    profile.mkdir(parents=True)
    (profile / "prefs.js").write_text(
        '// Mozilla User Preferences\nuser_pref("browser.startup.page", 3);\n',
        encoding="utf-8",
    )
    root.mkdir(parents=True, exist_ok=True)
    (root / "profiles.ini").write_text(
        "[Profile0]\nName=default-release\nIsRelative=1\n"
        f"Path={name}\nDefault=1\n",
        encoding="utf-8",
    )
    return profile


@pytest.fixture
def firefox_home(tmp_path, monkeypatch, offline) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(firefox, "HOME", home)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "xdg-config"))
    monkeypatch.setattr(
        firefox, "offline", lambda *parts: Path(offline, *parts)
    )
    return home


def test_discovers_xdg_native_flatpak_snap_and_orphan_profiles(
    firefox_home, monkeypatch,
):
    xdg_native = _seed_profile(
        firefox_home / "xdg-config/mozilla/firefox", "xdg.default"
    )
    native = _seed_profile(firefox_home / ".mozilla/firefox", "native.default")
    flatpak = _seed_profile(
        firefox_home / ".var/app/org.mozilla.firefox/.mozilla/firefox",
        "flatpak.default",
    )
    snap = _seed_profile(
        firefox_home / "snap/firefox/common/.mozilla/firefox",
        "snap.default",
    )
    orphan = native.parent / "orphan.dev-edition"
    orphan.mkdir()
    (orphan / "prefs.js").write_text("", encoding="utf-8")

    assert firefox.discover_profiles() == sorted(
        (
            xdg_native.resolve(), native.resolve(), flatpak.resolve(),
            orphan.resolve(), snap.resolve(),
        ),
        key=str,
    )

    monkeypatch.delenv("XDG_CONFIG_HOME")
    default_xdg = _seed_profile(
        firefox_home / ".config/mozilla/firefox", "xdg.default"
    )
    assert firefox.discover_profiles() == sorted(
        (
            default_xdg.resolve(), native.resolve(), flatpak.resolve(),
            orphan.resolve(), snap.resolve(),
        ),
        key=str,
    )


def test_discovers_absolute_registered_profile(firefox_home):
    root = firefox_home / ".mozilla/firefox"
    external = firefox_home / "Browser Profiles/work"
    external.mkdir(parents=True)
    (external / "prefs.js").write_text("", encoding="utf-8")
    root.mkdir(parents=True)
    (root / "profiles.ini").write_text(
        f"[Profile0]\nIsRelative=0\nPath={external}\n",
        encoding="utf-8",
    )

    assert firefox.discover_profiles() == [external.resolve()]


def test_does_not_scan_tor_browser_profiles(firefox_home):
    tor = firefox_home / ".local/share/torbrowser/profile.default"
    tor.mkdir(parents=True)
    (tor / "prefs.js").write_text("", encoding="utf-8")

    assert firefox.discover_profiles() == []


def test_install_preserves_css_and_browser_data_then_uninstall_restores(
    firefox_home,
):
    profile = _seed_profile(firefox_home / ".mozilla/firefox")
    chrome = profile / "chrome"
    chrome.mkdir()
    original_chrome = '@charset "UTF-8";\n/* mine */\n#nav-bar { color: red; }\n'
    original_content = "/* my content CSS */\n"
    original_user = 'user_pref("browser.compactmode.show", true);\n'
    (chrome / "userChrome.css").write_text(original_chrome, encoding="utf-8")
    (chrome / "userContent.css").write_text(original_content, encoding="utf-8")
    (profile / "user.js").write_text(original_user, encoding="utf-8")
    places = profile / "places.sqlite"
    places.write_bytes(b"browser-history-must-not-change")

    firefox.install()

    installed_chrome = (chrome / "userChrome.css").read_text(encoding="utf-8")
    assert installed_chrome.startswith('@charset "UTF-8";\n' + firefox.CHROME_START)
    assert original_chrome.split("\n", 1)[1] in installed_chrome
    assert installed_chrome.count(firefox.CHROME_START) == 1
    assert firefox.CHROME_START in (chrome / "userContent.css").read_text()
    assert original_user in (profile / "user.js").read_text()
    assert firefox.USER_START in (profile / "user.js").read_text()
    assert (chrome / firefox.THEME_DIRNAME / firefox.OWNERSHIP_MARKER).is_file()
    assert places.read_bytes() == b"browser-history-must-not-change"

    # Reinstall is idempotent and leaves the user's additions intact.
    with (chrome / "userChrome.css").open("a", encoding="utf-8") as handle:
        handle.write("/* added after install */\n")
    firefox.install()
    assert (chrome / "userChrome.css").read_text().count(firefox.CHROME_START) == 1

    firefox.uninstall()

    restored_chrome = (chrome / "userChrome.css").read_text(encoding="utf-8")
    assert firefox.CHROME_START not in restored_chrome
    assert "#nav-bar { color: red; }" in restored_chrome
    assert "added after install" in restored_chrome
    assert (chrome / "userContent.css").read_text() == original_content
    assert (profile / "user.js").read_text() == original_user
    assert not (chrome / firefox.THEME_DIRNAME).exists()
    assert places.read_bytes() == b"browser-history-must-not-change"
    assert not firefox._manifest_path().exists()
    assert len(list((firefox._state_root() / "snapshots").iterdir())) == 2


def test_install_and_uninstall_profile_without_existing_chrome(firefox_home):
    profile = _seed_profile(firefox_home / ".mozilla/firefox")

    firefox.install()
    assert (profile / "chrome/userChrome.css").is_file()
    assert (profile / "user.js").is_file()

    firefox.uninstall()
    assert not (profile / "chrome").exists()
    assert not (profile / "user.js").exists()
    assert (profile / "prefs.js").is_file()


def test_shared_chrome_symlink_is_detached_without_mutating_target(firefox_home):
    profile = _seed_profile(firefox_home / ".mozilla/firefox")
    shared = firefox_home / "shared-firefox-chrome"
    shared.mkdir()
    (shared / "userChrome.css").write_text("/* shared original */\n")
    (profile / "chrome").symlink_to(shared)

    firefox.install()

    assert (profile / "chrome").is_dir()
    assert not (profile / "chrome").is_symlink()
    assert firefox.CHROME_START in (profile / "chrome/userChrome.css").read_text()
    assert (shared / "userChrome.css").read_text() == "/* shared original */\n"
    assert not (shared / firefox.THEME_DIRNAME).exists()

    firefox.uninstall()
    assert (profile / "chrome/userChrome.css").read_text() == "/* shared original */\n"


def test_legacy_vinceliuice_symlink_migrates_and_uninstalls_to_normal_firefox(
    firefox_home,
):
    profile = _seed_profile(firefox_home / ".mozilla/firefox")
    shared = profile.parent / "firefox-themes"
    shared.mkdir()
    legacy_css = '@import "MacTahoe/theme.css";\n/* old theme */\n'
    (shared / "userChrome.css").write_text(legacy_css, encoding="utf-8")
    (shared / "MacTahoe").mkdir()
    (shared / "MacTahoe/theme.css").write_text("/* old payload */\n")
    (profile / "chrome").symlink_to(shared)
    (profile / "user.js").write_text(
        "\n".join(firefox.LEGACY_PREF_LINES) + "\n", encoding="utf-8"
    )

    firefox.install()

    assert not (profile / "chrome").is_symlink()
    assert legacy_css not in (profile / "chrome/userChrome.css").read_text()
    user_js = (profile / "user.js").read_text()
    assert firefox.USER_START in user_js
    assert 'browser.tabs.drawInTitlebar' not in user_js
    # The old shared payload is preserved on disk and in the timestamped backup.
    assert (shared / "userChrome.css").read_text() == legacy_css
    snapshots = list((firefox._state_root() / "snapshots").glob("*/*/chrome"))
    assert snapshots and (snapshots[0] / "userChrome.css").read_text() == legacy_css

    firefox.uninstall()

    assert not (profile / "chrome").exists()
    assert not (profile / "user.js").exists()
    assert (profile / "prefs.js").is_file()
    assert (shared / "MacTahoe/theme.css").read_text() == "/* old payload */\n"


def test_existing_same_named_directory_is_backed_up_and_restored(firefox_home):
    profile = _seed_profile(firefox_home / ".mozilla/firefox")
    collision = profile / "chrome" / firefox.THEME_DIRNAME
    collision.mkdir(parents=True)
    (collision / "mine.txt").write_text("keep me", encoding="utf-8")

    firefox.install()
    assert not (collision / "mine.txt").exists()
    assert (collision / firefox.OWNERSHIP_MARKER).is_file()

    firefox.uninstall()
    assert (collision / "mine.txt").read_text() == "keep me"
    assert not (collision / firefox.OWNERSHIP_MARKER).exists()


def test_backup_failure_skips_profile_without_writing(firefox_home, monkeypatch):
    profile = _seed_profile(firefox_home / ".mozilla/firefox")
    before = (profile / "prefs.js").read_bytes()
    monkeypatch.setattr(firefox, "_snapshot_profile", lambda profile, root: None)

    firefox.install()

    assert not (profile / "chrome").exists()
    assert not (profile / "user.js").exists()
    assert (profile / "prefs.js").read_bytes() == before


def test_lost_manifest_does_not_make_owned_payload_user_data(firefox_home):
    profile = _seed_profile(firefox_home / ".mozilla/firefox")
    firefox.install()
    firefox._manifest_path().unlink()

    firefox.install()
    firefox.uninstall()

    assert not (profile / "chrome" / firefox.THEME_DIRNAME).exists()
    assert not (profile / "chrome/userChrome.css").exists()
    assert not (profile / "chrome/userContent.css").exists()
    assert not (profile / "user.js").exists()


def test_failed_payload_swap_rolls_back_preexisting_directory(
    firefox_home, monkeypatch,
):
    profile = _seed_profile(firefox_home / ".mozilla/firefox")
    collision = profile / "chrome" / firefox.THEME_DIRNAME
    collision.mkdir(parents=True)
    (collision / "mine.txt").write_text("not disposable", encoding="utf-8")
    real_replace = firefox.os.replace

    def fail_staged_payload(source, destination):
        if Path(source).name == f".{firefox.THEME_DIRNAME}.mttkde-stage":
            raise OSError("simulated atomic swap failure")
        return real_replace(source, destination)

    monkeypatch.setattr(firefox.os, "replace", fail_staged_payload)
    firefox.install()

    assert (collision / "mine.txt").read_text() == "not disposable"
    assert not (profile / "chrome/userChrome.css").exists()


def test_malformed_existing_managed_marker_is_never_truncated(firefox_home):
    profile = _seed_profile(firefox_home / ".mozilla/firefox")
    chrome = profile / "chrome"
    chrome.mkdir()
    broken = firefox.CHROME_START + "\n/* no closing marker */\n"
    (chrome / "userChrome.css").write_text(broken, encoding="utf-8")

    firefox.install()

    assert (chrome / "userChrome.css").read_text() == broken
    assert not (chrome / firefox.THEME_DIRNAME).exists()
    assert (profile / "prefs.js").is_file()


def test_bundled_fork_has_license_provenance_and_complete_entrypoints(offline):
    root = offline / "firefox"
    theme = root / firefox.THEME_DIRNAME
    provenance = (root / "UPSTREAM.md").read_text(encoding="utf-8")
    marker = json.loads((theme / firefox.OWNERSHIP_MARKER).read_text())

    assert (root / "LICENSE.MacTahoe").is_file()
    assert "MacTahoe-gtk-theme" in provenance
    assert marker["upstream_commit"] == "aaac1c5451fc2f14e02ec1d9b606baa41589cd41"
    assert (theme / "userChrome.css").is_file()
    assert (theme / "userContent.css").is_file()
    assert (theme / "MacTahoe/theme.css").is_file()
    assert len(list((theme / "MacTahoe/icons").glob("*.svg"))) > 50
