"""Installed equivalents and explicit, optional Dock application provisioning.

SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import configparser
import os
from pathlib import Path
import shutil
import subprocess

from localization import tr
from log import warn
from utils import check_cancelled, pkg_install, run_user

# Kept in sync with the standalone Plasma scripts by test_dock_apps.py.
CANDIDATES = {'files': ['org.kde.dolphin.desktop',
           'org.gnome.Nautilus.desktop',
           'thunar.desktop',
           'pcmanfm-qt.desktop'],
 'browser': ['firefox.desktop',
             'firefox-esr.desktop',
             'org.mozilla.firefox.desktop',
             'firefox_firefox.desktop',
             'chromium.desktop',
             'chromium-browser.desktop',
             'google-chrome.desktop',
             'com.google.Chrome.desktop',
             'brave-browser.desktop',
             'com.brave.Browser.desktop',
             'org.kde.falkon.desktop'],
 'mail': ['thunderbird.desktop',
          'org.mozilla.Thunderbird.desktop',
          'thunderbird_thunderbird.desktop',
          'org.kde.kmail2.desktop',
          'org.gnome.Evolution.desktop',
          'org.gnome.Geary.desktop'],
 'calendar': ['org.kde.merkuro.calendar.desktop',
              'org.kde.korganizer.desktop',
              'org.gnome.Calendar.desktop'],
 'notes': ['org.kde.marknote.desktop',
           'org.kde.knotes.desktop',
           'org.gnome.Gnote.desktop',
           'org.gnome.Notes.desktop',
           'com.vixalien.sticky.desktop'],
 'photos': ['org.kde.gwenview.desktop',
            'org.gnome.Loupe.desktop',
            'org.gnome.eog.desktop',
            'org.xfce.ristretto.desktop',
            'ristretto.desktop',
            'nomacs.desktop'],
 'music': ['org.kde.elisa.desktop',
           'org.gnome.Rhythmbox3.desktop',
           'org.gnome.Music.desktop',
           'io.bassi.Amberol.desktop',
           'org.strawberrymusic.strawberry.desktop',
           'strawberry.desktop',
           'clementine.desktop',
           'audacious.desktop'],
 'video': ['org.kde.haruna.desktop',
           'org.gnome.Showtime.desktop',
           'vlc.desktop',
           'org.videolan.VLC.desktop',
           'org.gnome.Totem.desktop',
           'io.github.celluloid_player.Celluloid.desktop',
           'mpv.desktop',
           'smplayer.desktop'],
 'store': ['org.kde.discover.desktop', 'org.gnome.Software.desktop'],
 'settings': ['systemsettings.desktop']}
OPTIONAL = ("mail", "calendar", "notes", "photos", "music", "video")
LABELS = dict(zip(OPTIONAL, ("Mail", "Calendar", "Notes", "Photos", "Music", "Video")))
FLATPAKS = {
    "mail": ("Thunderbird", "org.mozilla.Thunderbird"),
    "calendar": ("Merkuro", "org.kde.merkuro"),
    "notes": ("Marknote", "org.kde.marknote"),
    "photos": ("Gwenview", "org.kde.gwenview"),
    "music": ("Elisa", "org.kde.elisa"),
    "video": ("Haruna", "org.kde.haruna"),
}
FLATHUB = "https://dl.flathub.org/repo/flathub.flatpakrepo"


def application_roots() -> list[Path]:
    home = Path.home()
    data = Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share")
    roots = [data / "applications"]
    roots += [Path(p) / "applications" for p in
              (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") if p]
    roots += [data / "flatpak/exports/share/applications",
              Path("/var/lib/flatpak/exports/share/applications")]
    return list(dict.fromkeys(p for p in roots if p.is_absolute()))


def installed_apps(roots: list[Path] | None = None) -> dict[str, str]:
    """Honor user desktop overrides, including Hidden entries, before system ones."""
    entries = {}
    for root in application_roots() if roots is None else roots:
        for file in sorted(root.glob("**/*.desktop")):
            desktop_id = str(file.relative_to(root)).replace("/", "-")
            if desktop_id in entries:
                continue
            entries[desktop_id] = None
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read_string(file.read_text(encoding="utf-8"))
                entry = parser["Desktop Entry"]
                if entry.get("Type") != "Application" or entry.getboolean("Hidden", False):
                    continue
                if entry.getboolean("NoDisplay", False):
                    continue
                executable = entry.get("TryExec")
                if executable and not shutil.which(executable):
                    continue
                if not entry.get("Exec") and not entry.getboolean("DBusActivatable", False):
                    continue
                entries[desktop_id] = entry.get("Name", desktop_id)
            except (OSError, UnicodeError, configparser.Error, KeyError, ValueError):
                continue
    return {category: next((entries[c] for c in candidates if entries.get(c)), "")
            for category, candidates in CANDIDATES.items()}


def recommendation(category: str, source: str) -> tuple[str, str] | None:
    if source == "flatpak":
        return FLATPAKS.get(category)
    from distro import dock_app_package
    return dock_app_package(category)


def _flatpak(*args: str) -> subprocess.CompletedProcess:
    return run_user(["flatpak", *args], stdin=subprocess.DEVNULL,
                    capture_output=True, text=True, check=False)


def _prepare_flatpak(add_flathub: bool) -> bool:
    if not shutil.which("flatpak"):
        from distro import dock_app_package
        runtime = dock_app_package("flatpak")
        if not runtime or not pkg_install(runtime[1]) or not shutil.which("flatpak"):
            return False
    result = _flatpak("remotes", "--user", "--columns=name,url")
    if result.returncode:
        return False
    for line in result.stdout.splitlines():
        fields = line.split()
        if fields and fields[0] == "flathub":
            return len(fields) == 2 and fields[1].rstrip("/") in (
                "https://dl.flathub.org/repo", "https://flathub.org/repo")
    return add_flathub and _flatpak("remote-add", "--user", "--if-not-exists",
                                   "flathub", FLATHUB).returncode == 0


def install_selected(choices: dict) -> None:
    """Only fixed category IDs cross the UI/backend boundary; never arbitrary packages."""
    from installer_choices import validate
    choices = validate(choices)
    if not choices["dock"]:
        return
    source = choices["dock_apps_source"]
    ready = None
    for category in choices["dock_apps"]:
        check_cancelled()
        if installed_apps().get(category):
            continue
        proposal = recommendation(category, source)
        try:
            if proposal is None:
                raise RuntimeError("unsupported package mapping")
            name, package = proposal
            if source == "native":
                success = pkg_install(package)
            else:
                if ready is None:
                    ready = _prepare_flatpak(choices["dock_add_flathub"])
                success = ready and _flatpak("install", "--user", "--noninteractive", "--assumeyes",
                                            "flathub", package).returncode == 0
            if not success or not installed_apps().get(category):
                raise RuntimeError("application unavailable")
        except (OSError, subprocess.SubprocessError, RuntimeError):
            warn(tr("Could not add {app}. The theme will continue; this Dock category remains pending.",
                    app=proposal[0] if proposal else LABELS[category]))
            # Do not silently switch repositories or sources after consent.
