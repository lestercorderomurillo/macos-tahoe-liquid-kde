"""Installer step: copy the Python theme-switch + systemd units into ~/.local."""

import shutil
import subprocess
from pathlib import Path

from paths import REPO_ROOT
from steps._helpers import HOME, kw_write, ok, offline, theme_mode, warn
from utils import run_user

BIN_DEST = HOME / ".local/bin/mac-tahoe-theme-switch"
SVC_DIR = HOME / ".config/systemd/user"
PY_SRC = REPO_ROOT / "src/scripts/theme_switch.py"

# --auto only: one service (oneshot, fires 10s after plasmashell is up)
# + one timer (06:00 / 18:00). Both point at the same binary; --light
# and --dark skip the install entirely because the user has pinned the
# mode and there is nothing to schedule.
UNITS = (
    "mac-tahoe-liquid-kde-theme.service",
    "mac-tahoe-liquid-kde-theme.timer",
)


def install() -> None:
    BIN_DEST.parent.mkdir(parents=True, exist_ok=True)
    if PY_SRC.is_file():
        shutil.copy2(PY_SRC, BIN_DEST)
        BIN_DEST.chmod(0o755)
    SVC_DIR.mkdir(parents=True, exist_ok=True)

    auto = theme_mode() == "auto"

    if auto:
        for u in UNITS:
            src = offline(u)
            if src.is_file():
                shutil.copy2(src, SVC_DIR / u)
        run_user(["systemctl", "--user", "daemon-reload"],
                 check=False,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for verb in ("enable", "start"):
            run_user(
                ["systemctl", "--user", verb,
                 "mac-tahoe-liquid-kde-theme.service",
                 "mac-tahoe-liquid-kde-theme.timer"],
                check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    else:
        # Explicit --light / --dark: user has pinned the mode. No
        # scheduler to install — and if a previous --auto install left
        # the units behind, tear them down so they can't fight the
        # pinned mode on the next login.
        for unit in UNITS:
            run_user(
                ["systemctl", "--user", "disable", "--now", unit],
                check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            try: (SVC_DIR / unit).unlink()
            except FileNotFoundError: pass
            except OSError: pass
        run_user(["systemctl", "--user", "daemon-reload"],
                 check=False,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if BIN_DEST.is_file() and BIN_DEST.stat().st_mode & 0o111:
        ok("Theme switcher installed")
    else:
        warn("Theme switcher not installed")


_LEGACY_BIN = HOME / ".local/bin/mactahoe-theme-switch"


def uninstall() -> None:
    # Include legacy unit names from earlier versions so an upgrade-then-
    # uninstall doesn't leave orphaned systemd files behind.
    legacy_units = (
        *UNITS,
        "mac-tahoe-liquid-kde-theme-apply.service",
        "mactahoe-theme-watcher.service",
    )
    for unit in legacy_units:
        run_user(
            ["systemctl", "--user", "disable", "--now", unit],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try: (SVC_DIR / unit).unlink()
        except FileNotFoundError: pass
        except OSError: pass
    run_user(["systemctl", "--user", "daemon-reload"],
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
