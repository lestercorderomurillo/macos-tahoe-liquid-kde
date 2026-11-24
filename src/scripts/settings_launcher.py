"""Install the desktop entry that opens the shared settings window."""

from pathlib import Path
import os
import shlex
import sys

from glass_surface_settings import atomic_write

COMMAND = "mac-tahoe-settings"
DESKTOP_ENTRY = "org.kde.mac-tahoe-liquid-kde.settings.desktop"
BINARY_MARKER = "# Installed by MacTahoe Liquid KDE"
DESKTOP_MARKER = "X-Mactahoe-Owned=true"


def _installed_source_record():
    state = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    return state / "mac-tahoe-liquid-kde/settings-source"


def _paths():
    home = Path.home()
    data = Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share")
    return home / ".local/bin" / COMMAND, data / "applications" / DESKTOP_ENTRY


def install(source):
    source = Path(source).resolve()
    launcher = source / "installer"
    binary, desktop = _paths()
    if not launcher.is_file():
        raise FileNotFoundError(launcher)
    for path, marker in ((binary, BINARY_MARKER), (desktop, DESKTOP_MARKER)):
        if path.is_symlink() or (path.exists() and marker not in path.read_text(encoding="utf-8")):
            raise ValueError(f"Refusing to replace an unmanaged Settings launcher: {path}")
    command = shlex.join((sys.executable, str(launcher), "--mode=settings"))
    script = (f"#!/bin/sh\n{BINARY_MARKER}\n"
              + "if [ \"$1\" = --available ]; then exec test -r " + shlex.quote(str(launcher)) + "; fi\n"
              + "exec " + command + ' "$@"\n')
    atomic_write(binary, script.encode())
    binary.chmod(0o755)
    # Desktop entry double quotes and field-code expansion have different
    # escaping rules from shell commands.
    quoted = str(binary).replace("\\", "\\\\").replace('"', '\\"')
    quoted = quoted.replace("$", "\\$").replace("`", "\\`").replace("%", "%%")
    content = ("[Desktop Entry]\nType=Application\nName=Liquid KDE Settings\n"
               "Name[es]=Ajustes de Liquid KDE\nIcon=preferences-system\n"
               f'Exec="{quoted}"\nTryExec={binary}\nCategories=Settings;DesktopSettings;\n{DESKTOP_MARKER}\n')
    atomic_write(desktop, content.encode())
    # The panel can still open the installed edition if its shortcut disappears.
    # Golden Gate also uses this record to protect its active staged checkout.
    atomic_write(_installed_source_record(), os.fsencode(source) + b"\n")


def uninstall():
    for path, marker in zip(_paths(), (BINARY_MARKER, DESKTOP_MARKER)):
        if path.is_file() and not path.is_symlink() and marker in path.read_text(encoding="utf-8"):
            path.unlink(missing_ok=True)
    _installed_source_record().unlink(missing_ok=True)
