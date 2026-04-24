import subprocess

from installer.steps._helpers import HOME, fail, have, ok

CONF_DIR = HOME / ".config/xdg-desktop-portal"
CONF_FILE = CONF_DIR / "kde-portals.conf"


# Routing rules:
#   Settings → gtk : libadwaita queries Settings for gtk-decoration-layout /
#       gtk-theme / color-scheme. portal-kde answers with KDE's own schema
#       (Aurorae "XIA" button layout), which libadwaita can't parse → the
#       buttons fall back to right-side close-only and the mac traffic
#       lights disappear. portal-gtk reads gsettings and returns the
#       "close,minimize,maximize:" format libadwaita expects.
#   FileChooser / AppChooser → kde : "Open with…" and file pickers render
#       as native Qt/KDE dialogs instead of the stale GTK/Nautilus ones.
#   No `default=…` so other portals fall back to their compiled-in default.
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
        subprocess.run(
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
