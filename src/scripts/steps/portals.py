import os
import signal
import subprocess
from pathlib import Path

from distro import user_service_manager_command
from steps._helpers import HOME, fail, ok
from utils import run_user

CONF_DIR = HOME / ".config/xdg-desktop-portal"
CONF_FILE = CONF_DIR / "kde-portals.conf"


# Settings → gtk: portal-kde answers with Aurorae's "XIA" button layout, which
# libadwaita can't parse (mac traffic lights vanish); portal-gtk returns the
# "close,minimize,maximize:" form it expects.
# FileChooser / AppChooser → kde: native Qt dialogs. No `default=` line so
# other portals keep their compiled-in default.
ROUTING = """\
[preferred]
org.freedesktop.impl.portal.Settings=gtk
org.freedesktop.impl.portal.FileChooser=kde
org.freedesktop.impl.portal.AppChooser=kde
"""

PORTAL_SERVICES = (
    "xdg-desktop-portal",
    "xdg-desktop-portal-kde",
    "xdg-desktop-portal-gtk",
)
_PROC_ROOT = Path("/proc")


def _bounce_services() -> None:
    command_prefix = user_service_manager_command("restart")
    if command_prefix is not None:
        manager_ok = True
        for svc in PORTAL_SERVICES:
            try:
                result = run_user(
                    [*command_prefix, svc], check=False, timeout=8,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                manager_ok = result.returncode == 0 and manager_ok
            except (OSError, subprocess.TimeoutExpired):
                manager_ok = False
        if manager_ok:
            return

    # OpenRC and other non-systemd sessions rely on D-Bus activation. This is
    # also the fallback for a temporarily unavailable systemd user manager.
    # Stop only matching same-user portal processes; the next portal request
    # starts them again with the new routing config.
    try:
        uid = int(os.environ.get("SUDO_UID") or os.getuid())
    except ValueError:
        uid = os.getuid()
    wanted = set(PORTAL_SERVICES)
    try:
        processes = list(_PROC_ROOT.iterdir())
    except OSError:
        return
    for process in processes:
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != uid:
                continue
            argv0 = (process / "cmdline").read_bytes().split(b"\0", 1)[0]
            name = Path(os.fsdecode(argv0)).name
            if name in wanted:
                os.kill(int(process.name), signal.SIGTERM)
        except (OSError, ValueError):
            continue


def install() -> None:
    CONF_DIR.mkdir(parents=True, exist_ok=True)
    try:
        CONF_FILE.write_text(ROUTING)
    except OSError as exc:
        fail(f"KDE portal routing: {exc}")
        return
    ok("KDE portal routing installed")
    _bounce_services()


def uninstall() -> None:
    if CONF_FILE.is_file():
        try:
            CONF_FILE.unlink()
            ok("KDE portal routing removed")
        except OSError:
            fail("KDE portal routing")
    else:
        ok("KDE portal routing (not installed)")
    _bounce_services()
