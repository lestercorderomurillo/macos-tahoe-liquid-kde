"""Embedded kconf_update scripts for config migrations.

The installer used to scrub legacy config with hand-written regex inside
apply.py / theme_switch.py / plasmoids.py. Those regexes are brittle: a
format change in kdeglobals or appletsrc across a Plasma upgrade can break
them silently. The migrations now live in POSIX shell helpers under
src/offline/kconf_update/ with .upd descriptors installed to
~/.local/share/kconf_update, so kded's kconf_update pass picks them up at
login (KF6 contract: Version=6 header, scripts invoked with no arguments
and self-locating their config files).

The installer never invokes the kconf_update binary itself: it lives in
libexec (not on PATH) on most distros, and install/uninstall need the
effect immediately anyway, so the step runs the bundled helpers directly
with explicit targets. The helpers are idempotent, so the later login-time
kconf_update pass is a harmless re-run.
"""

import subprocess
from pathlib import Path

from steps._helpers import DATA_HOME, HOME, feat_enabled, install_tree, offline, ok
from utils import kw_read, kw_write, qdbus_call, run_user

KCONF_UPDATE_DIR = DATA_HOME / "kconf_update"
BUNDLE = offline("kconf_update")

_SCRIPTS = (
    "mac-tahoe-scrub-kdedefaults.sh",
    "mac-tahoe-scrub-colorgroups.sh",
    "mac-tahoe-migrate-appletsrc.sh",
)

_V038_ROUNDED_CORNERS_PRESET = (
    ("Size", "22"),
    ("InactiveCornerRadius", "22"),
    ("UseSquircleShape", "true"),
    ("Squircleness", "0.55"),
    ("IncludeDialogs", "false"),
    ("OutlineThickness", "0"),
    ("InactiveOutlineThickness", "0"),
    ("SecondOutlineThickness", "0"),
    ("InactiveSecondOutlineThickness", "0"),
    ("OuterOutlineThickness", "0"),
    ("InactiveOuterOutlineThickness", "0"),
)


def deps():
    return []


def _enabled_scripts() -> tuple[str, ...]:
    # The dock-ID rename only makes sense when the fork dock ships: without
    # plasmoids it would point stock applets at a plugin that never installs.
    if feat_enabled("PLASMOIDS"):
        return _SCRIPTS
    return tuple(s for s in _SCRIPTS if s != "mac-tahoe-migrate-appletsrc.sh")


def rollback_v038_border_sync() -> bool:
    """Remove only the exact cross-theme border preset shipped in v0.38.

    If any preset value differs, the Round-Corners group is user-customized
    and remains untouched. The effect's enabled state is always preserved.
    """
    exact_match = all(
        kw_read("kwinrc", "Round-Corners", key) == value
        for key, value in _V038_ROUNDED_CORNERS_PRESET
    )
    if exact_match:
        for key, _value in _V038_ROUNDED_CORNERS_PRESET:
            kw_write(
                "--file", "kwinrc", "--group", "Round-Corners",
                "--key", key, "--delete",
            )
        ok("v0.38 Rounded Corners border preset removed")

    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")
    return exact_match


def install() -> None:
    rollback_v038_border_sync()
    if not BUNDLE.is_dir():
        return
    install_tree(BUNDLE, KCONF_UPDATE_DIR, "kconf_update scripts")
    for name in set(_SCRIPTS) - set(_enabled_scripts()):
        for f in (KCONF_UPDATE_DIR / name,
                  KCONF_UPDATE_DIR / (name[:-3] + ".upd")):
            try:
                f.unlink()
            except OSError:
                pass
    run_migrations()


def uninstall() -> None:
    # Remove only our entries: ~/.local/share/kconf_update is a shared dir.
    if not KCONF_UPDATE_DIR.is_dir():
        return
    for f in KCONF_UPDATE_DIR.glob("mac-tahoe-*"):
        try:
            f.unlink()
        except OSError:
            pass


def run_migration(name: str) -> None:
    """Run one bundled helper directly on its live config files."""
    script = BUNDLE / name
    if not script.is_file():
        return
    for target in _targets_for(name):
        if target.is_file():
            run_user(["sh", str(script), str(target)], check=False,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_migrations() -> None:
    for name in _enabled_scripts():
        run_migration(name)


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
