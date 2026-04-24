"""Installer step: copy the Python theme-switch + systemd units into ~/.local."""

import shutil
import subprocess
from pathlib import Path

from paths import REPO_ROOT
from steps._helpers import HOME, kw_write, ok, offline, theme_mode, warn

BIN_DEST = HOME / ".local/bin/mac-tahoe-theme-switch"
SVC_DIR = HOME / ".config/systemd/user"
PY_SRC = REPO_ROOT / "src/scripts/theme_switch.py"

# The watch service handles manual user overrides; the timer + apply
# service handle the 06:00 / 18:00 transitions even across reboots,
# suspends, and late logins.
UNITS = (
    "mac-tahoe-liquid-kde-theme.service",
    "mac-tahoe-liquid-kde-theme.timer",
    "mac-tahoe-liquid-kde-theme-apply.service",
)


def install() -> None:
    BIN_DEST.parent.mkdir(parents=True, exist_ok=True)
    if PY_SRC.is_file():
        shutil.copy2(PY_SRC, BIN_DEST)
        BIN_DEST.chmod(0o755)
    SVC_DIR.mkdir(parents=True, exist_ok=True)
    for u in UNITS:
        src = offline(u)
        if src.is_file():
            shutil.copy2(src, SVC_DIR / u)

    subprocess.run(["systemctl", "--user", "daemon-reload"],
                   check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if theme_mode() == "auto":
        for verb in ("enable", "start"):
            subprocess.run(
                ["systemctl", "--user", verb,
                 "mac-tahoe-liquid-kde-theme.service",
                 "mac-tahoe-liquid-kde-theme.timer"],
                check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    else:
        # Explicit light/dark: user owns the preference, no scheduler.
        for unit in ("mac-tahoe-liquid-kde-theme.service",
                     "mac-tahoe-liquid-kde-theme.timer"):
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", unit],
                check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

    if BIN_DEST.is_file() and BIN_DEST.stat().st_mode & 0o111:
        ok("Theme switcher installed")
    else:
        warn("Theme switcher not installed")


_LEGACY_BIN = HOME / ".local/bin/mactahoe-theme-switch"


def uninstall() -> None:
    legacy_units = (*UNITS, "mactahoe-theme-watcher.service")
    for unit in legacy_units:
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", unit],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try: (SVC_DIR / unit).unlink()
        except FileNotFoundError: pass
        except OSError: pass
    subprocess.run(["systemctl", "--user", "daemon-reload"],
                   check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for p in (BIN_DEST, _LEGACY_BIN):
        try: p.unlink()
        except FileNotFoundError: pass
        except OSError: pass

    kw_write("--file", "kdeglobals", "--group", "KDE",
             "--key", "AutomaticLookAndFeel", "false")
    kw_write("--file", "kdeglobals", "--group", "KDE",
             "--key", "DefaultLightLookAndFeel", "--delete")
    kw_write("--file", "kdeglobals", "--group", "KDE",
             "--key", "DefaultDarkLookAndFeel", "--delete")
    ok("Theme switcher removed")
