"""Embedded kconf_update scripts for config migrations.

The installer used to scrub legacy config with hand-written regex inside
apply.py / theme_switch.py / plasmoids.py. Those regexes are brittle: a
format change in kdeglobals or appletsrc across a Plasma upgrade can break
them silently. KDE's official migration tool is kconf_update, which kded
runs at login, so the migrations survive Plasma upgrades.

This step installs the bundled .upd scripts into the user kconf_update data
dir and runs kconf_update. When the binary is missing (minimal / CI systems)
it runs the helper scripts directly on the live config files, preserving the
offline behaviour.
"""

import subprocess
from pathlib import Path

from steps._helpers import HOME, install_tree, offline, warn
from utils import have, run_user

KCONF_UPDATE_DIR = HOME / ".local/share/kconf_update"
BUNDLE = offline("kconf_update")

_SCRIPTS = (
    "mac-tahoe-scrub-kdedefaults.sh",
    "mac-tahoe-scrub-colorgroups.sh",
    "mac-tahoe-migrate-appletsrc.sh",
)


def deps():
    return []


def install() -> None:
    run_migrations()


def uninstall() -> None:
    if KCONF_UPDATE_DIR.is_dir():
        import shutil
        shutil.rmtree(KCONF_UPDATE_DIR, ignore_errors=True)


def run_migrations() -> None:
    """Install the bundled kconf_update scripts and run the migrations."""
    if not BUNDLE.is_dir():
        return
    install_tree(BUNDLE, KCONF_UPDATE_DIR, "kconf_update scripts")
    _run()


def _run() -> None:
    if have("kconf_update"):
        run_user(["kconf_update"], check=False,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    # Fallback: binary missing (minimal / CI). Run the helpers directly so
    # the migration still happens offline.
    _run_scripts_direct()


def _run_scripts_direct() -> None:
    for name in _SCRIPTS:
        script = KCONF_UPDATE_DIR / name
        if not script.is_file():
            continue
        for target in _targets_for(name):
            if target.is_file():
                run_user(["sh", str(script), str(target)], check=False,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _targets_for(name: str) -> list[Path]:
    if name == "mac-tahoe-scrub-kdedefaults.sh":
        base = HOME / ".config/kdedefaults"
        return [base / fn for fn in (
            "package", "kdeglobals", "plasmarc", "kcminputrc",
            "kwinrc", "ksplashrc", "kscreenlockerrc",
        )]
    if name == "mac-tahoe-scrub-colorgroups.sh":
        return [HOME / ".config/kdeglobals"]
    if name == "mac-tahoe-migrate-appletsrc.sh":
        return [HOME / ".config/plasma-org.kde.plasma.desktop-appletsrc"]
    return []
