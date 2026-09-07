"""Opt-in native GTK lifetime regression probe; never uses the live desktop.

Run with ``python tests/gtk_appmenu_probe.py``. Requires a C compiler,
pkg-config, GTK3 development files, appmenu-gtk-module, Xvfb, and
dbus-run-session. The unprotected control is expected to SIGSEGV on old
modules; core dumps are disabled in the native process. A distro carrying
the upstream residency fix will pass the control as well.
"""

import json
import os
from pathlib import Path
import resource
import select
import shlex
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src/scripts"))


def main() -> int:
    from distro import gtk3_appmenu_module
    from steps.globalmenu import _gtk_appmenu_environment

    for tool in ("cc", "pkg-config", "Xvfb", "dbus-run-session", "sh"):
        if not shutil.which(tool):
            print(f"Missing required tool: {tool}", file=sys.stderr)
            return 1
    module = gtk3_appmenu_module()
    if module is None:
        print("No installed GTK3 appmenu module found", file=sys.stderr)
        return 1
    flags = subprocess.check_output(
        ["pkg-config", "--cflags", "--libs", "gtk+-3.0"], text=True, timeout=10)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    with tempfile.TemporaryDirectory(prefix="mttkde-gtk-probe-") as tmp:
        folder = Path(tmp)
        binary = folder / "gtk-appmenu-lifetime"
        subprocess.run(
            ["cc", "-Wall", "-Wextra", "-Werror", "-o", str(binary),
             str(REPO / "tests/native/gtk_appmenu_lifetime.c"), *shlex.split(flags)],
            check=True, timeout=30)
        hook = folder / "mac-tahoe-gtk-appmenu.sh"
        hook.write_text(_gtk_appmenu_environment(module), encoding="utf-8")
        runtime = folder / "runtime"
        runtime.mkdir(mode=0o700)
        read_fd, write_fd = os.pipe()
        try:
            server = subprocess.Popen(
                ["Xvfb", "-displayfd", str(write_fd), "-screen", "0", "640x480x24",
                 "-nolisten", "tcp"], pass_fds=(write_fd,),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        finally:
            os.close(write_fd)
        try:
            with os.fdopen(read_fd) as display:
                if not select.select([display], [], [], 8)[0]:
                    raise RuntimeError("Private Xvfb startup timed out; local sockets may be blocked")
                number = display.readline().strip()
            if not number.isdigit():
                raise RuntimeError("Private Xvfb failed to start")
            environment = dict(
                os.environ, DISPLAY=":" + number, GDK_BACKEND="x11", GTK_THEME="Adwaita",
                GTK_USE_PORTAL="0", GIO_USE_VFS="local", GIO_USE_VOLUME_MONITOR="unix",
                XDG_CONFIG_HOME=str(folder), XDG_CONFIG_DIRS=str(folder),
                XDG_DATA_HOME=str(folder / "data"), XDG_CACHE_HOME=str(folder / "cache"),
                XDG_RUNTIME_DIR=str(runtime), GSETTINGS_BACKEND="memory", NO_AT_BRIDGE="1",
            )
            for key in ("GTK_MODULES", "GTK3_MODULES", "GTK_PATH", "G_DEBUG",
                        "UBUNTU_MENUPROXY", "DBUS_STARTER_ADDRESS", "DBUS_STARTER_BUS_TYPE",
                        "XAUTHORITY"):
                environment.pop(key, None)
            sourced = subprocess.check_output(
                ["sh", "-c", '. "$1"; exec "$2" -c "$3"', "gtk-hook-probe", str(hook),
                 sys.executable, 'import json, os; print(json.dumps(os.environ["GTK3_MODULES"]))'],
                env=environment, text=True, timeout=10)
            protected = dict(environment, GTK3_MODULES=json.loads(sourced))
            for label, current in (("settings only", environment), ("login hook", protected)):
                result = subprocess.run(
                    ["dbus-run-session", "--", str(binary)], env=current,
                    capture_output=True, text=True, timeout=10)
                print(f"{label}: exit={result.returncode}\n{result.stdout}", flush=True)
                if result.stderr:
                    print(result.stderr, file=sys.stderr)
                if "loaded: 1" not in result.stdout:
                    raise RuntimeError(f"{label}: the native module was not loaded")
                if label == "login hook":
                    if result.returncode != 0 or "after settings removal: 1" not in result.stdout:
                        raise RuntimeError("The login hook failed to keep the native module resident")
                elif result.returncode not in (0, 139):
                    raise RuntimeError(f"Unexpected control failure: {result.returncode}")
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
