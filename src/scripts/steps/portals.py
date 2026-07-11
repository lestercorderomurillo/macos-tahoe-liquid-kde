import subprocess

from steps._helpers import HOME, fail, have, ok
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


def _bounce_services() -> None:
    if not have("systemctl"):
        return
    for svc in PORTAL_SERVICES:
        run_user(
            ["systemctl", "--user", "restart", svc],
            check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )


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
