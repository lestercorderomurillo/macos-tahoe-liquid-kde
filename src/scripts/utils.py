import errno
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

from log import fail


def drop_privs_in_child() -> None:
    """``preexec_fn``: fully drop real+effective+saved UID/GID to SUDO_USER
    in the child. Mandatory — Qt6 aborts on ``getuid() != geteuid()``
    ("running setuid"), which the parent's euid-only drop would trigger."""
    sudo_uid = os.environ.get("SUDO_UID")
    sudo_gid = os.environ.get("SUDO_GID")
    if not sudo_uid or not sudo_gid:
        return
    uid = int(sudo_uid)
    gid = int(sudo_gid)
    # GID first: changing UID can drop the right to call setresgid.
    os.setresgid(gid, gid, gid)
    os.setresuid(uid, uid, uid)


def run_user(*args, **kwargs):
    """``subprocess.run`` that fully drops privileges in the child. Use for
    every Qt6/KDE child; skip only when the child genuinely needs root."""
    if "preexec_fn" not in kwargs:
        kwargs["preexec_fn"] = drop_privs_in_child
    return subprocess.run(*args, **kwargs)


_DESKTOP_ENV_KEYS = frozenset({
    "DBUS_SESSION_BUS_ADDRESS",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "XAUTHORITY",
    "XDG_CURRENT_DESKTOP",
    "XDG_RUNTIME_DIR",
    "XDG_SESSION_TYPE",
})
_PROC_ROOT = Path("/proc")


def restore_desktop_session_env(uid: int | None = None) -> None:
    """Recover a Plasma session environment without assuming an init system.

    ``sudo`` and cron strip the display and bus variables. The runtime-dir
    sockets recover Wayland/DBus on systemd and OpenRC/elogind; reading a
    same-user plasmashell's ``/proc/<pid>/environ`` fills X11/Xauthority and
    any remaining values. Permission and process-race failures are harmless.
    """
    if uid is None:
        try:
            uid = int(os.environ.get("SUDO_UID") or os.getuid())
        except ValueError:
            uid = os.getuid()
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{uid}")
    if runtime.is_dir():
        os.environ.setdefault("XDG_RUNTIME_DIR", str(runtime))
        bus = runtime / "bus"
        if "DBUS_SESSION_BUS_ADDRESS" not in os.environ and bus.is_socket():
            os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus}"
        if "WAYLAND_DISPLAY" not in os.environ:
            for socket in sorted(runtime.glob("wayland-*")):
                if socket.is_socket() and not socket.name.endswith(".lock"):
                    os.environ["WAYLAND_DISPLAY"] = socket.name
                    break

    try:
        candidates = list(_PROC_ROOT.iterdir())
    except OSError:
        return
    for process in candidates:
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != uid:
                continue
            if (process / "comm").read_text().strip() != "plasmashell":
                continue
            raw = (process / "environ").read_bytes()
        except OSError:
            continue
        for entry in raw.split(b"\0"):
            key_raw, sep, value_raw = entry.partition(b"=")
            if not sep:
                continue
            key = key_raw.decode(errors="ignore")
            if key not in _DESKTOP_ENV_KEYS or key in os.environ:
                continue
            value = value_raw.decode(errors="ignore")
            if value:
                os.environ[key] = value
        break


_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "MacTahoeLiquidKDE/installer"
)


# Hard retry ceiling: 60s timeouts + 1/2/4/8s backoff caps one fetch at
# ~5 min worst case.
MAX_FETCH_RETRIES = 5


def fetch(url: str, dest: Path | str, referer: str | None = None,
          retries: int = 3) -> bool:
    """Download ``url`` to ``dest`` with 1/2/4/8s backoff and Content-Length
    validation — flaky CDN edges truncate mid-stream without raising, so
    byte-count is the only truth. Partial files are deleted on final failure."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": _USER_AGENT}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    last_err: str = ""
    capped_retries = min(MAX_FETCH_RETRIES, max(1, retries))
    for attempt in range(capped_retries):
        if attempt > 0:
            time.sleep(2 ** (attempt - 1))
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                expected = r.headers.get("Content-Length")
                expected_n = int(expected) if expected and expected.isdigit() else None
                with dest.open("wb") as f:
                    shutil.copyfileobj(r, f)
            # Servers omitting Content-Length (chunked, gzip-on-the-fly)
            # skip the check — no ground truth for those.
            if expected_n is not None:
                actual_n = dest.stat().st_size
                if actual_n != expected_n:
                    last_err = (f"truncated: got {actual_n} of {expected_n} "
                                f"bytes")
                    continue
            return True
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last_err = f"{exc.__class__.__name__}: {exc}"
            continue
    if dest.exists():
        try:
            dest.unlink()
        except OSError:
            pass
    if last_err:
        print(f"     fetch {url}: {last_err}", file=sys.stderr)
    return False


def _staging_root() -> Path:
    """Resolve lazily — at import time HOME may still be /root (pre
    privilege-drop), which would cache a /root/.cache path and break
    every later safe_copy with PermissionError."""
    cache_home = (
        os.environ.get("XDG_CACHE_HOME")
        or os.path.expanduser("~/.cache")
    )
    return Path(cache_home) / "mac-tahoe-liquid-kde-staging"


def safe_copy(src: Path | str, dest: Path | str) -> bool:
    """Atomic copy via out-of-tree staging + rename, with rollback on failure.
    ``symlinks=True`` or icon themes balloon 2-3x and @2x lookup breaks; staging
    avoids dest.parent because plasmashell's KDirWatch scans sibling tmp dirs
    mid-copy and crashes loading half-built wallpaper packages."""
    src = Path(src)
    dest = Path(dest)
    parent = dest.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = _staging_root()
    staging.mkdir(parents=True, exist_ok=True)
    tmp = staging / f"tmp_{dest.name}_{os.getpid()}"
    bak = staging / f"bak_{dest.name}_{os.getpid()}"

    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    try:
        shutil.copytree(src, tmp, symlinks=True)
    except OSError:
        shutil.rmtree(tmp, ignore_errors=True)
        return False

    def _move(src_path: Path, dst_path: Path) -> None:
        try:
            src_path.rename(dst_path)
        except OSError as exc:
            if exc.errno == errno.EXDEV:
                shutil.move(str(src_path), str(dst_path))
            else:
                raise

    try:
        if dest.exists():
            try:
                _move(dest, bak)
            except OSError:
                shutil.rmtree(dest, ignore_errors=True)
        _move(tmp, dest)
    except OSError:
        if bak.exists():
            try:
                _move(bak, dest)
            except OSError:
                pass
        shutil.rmtree(tmp, ignore_errors=True)
        return False

    if bak.exists():
        shutil.rmtree(bak, ignore_errors=True)
    return True


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


# Session env vars exported by a live Plasma session. sudo strips these,
# so they're a positive signal only — absence doesn't mean "not Plasma".
_PLASMA_SESSION_ENV = (
    ("XDG_CURRENT_DESKTOP", "KDE"),
    ("XDG_SESSION_DESKTOP", "plasma"),
    ("KDE_FULL_SESSION", None),
    ("KDE_SESSION_VERSION", None),
)


def is_plasma_session() -> bool:
    """Whether this is a KDE Plasma host. Anchored on the plasmashell
    binary (sudo-proof), with the session env vars as a fallback."""
    if have("plasmashell"):
        return True
    for name, expected in _PLASMA_SESSION_ENV:
        value = os.environ.get(name, "")
        if not value:
            continue
        if expected is None or expected in value:
            return True
    return False


# Force non-interactive frontends so no install can block on a prompt
# (the GUI installer runs in an embedded terminal — a [Y/n] would hang).
_NONINTERACTIVE_ENV = {"DEBIAN_FRONTEND": "noninteractive"}


def _redirect_stream(stream):
    """Children inherit fd 1/2, which bypasses a Python-level sys.stdout
    redirect (the TUI progress screen routes install output to a log
    file). Hand the current stream to subprocess when it is a real file
    so package-manager output follows the redirect; None (= inherit)
    when it has no usable fd (pytest capture, plain terminal runs are
    unaffected either way)."""
    try:
        stream.fileno()
        return stream
    except (AttributeError, OSError, ValueError):
        return None


def _run_pkg_cmd(base: list[str], *args: str) -> bool:
    cmd = base if os.geteuid() == 0 else ["sudo", *base]
    cmd.extend(args)
    env = {**os.environ, **_NONINTERACTIVE_ENV}
    return subprocess.run(
        cmd, check=False, env=env, stdin=subprocess.DEVNULL,
        stdout=_redirect_stream(sys.stdout),
        stderr=_redirect_stream(sys.stderr),
    ).returncode == 0


def pkg_install(*pkgs: str) -> bool:
    """Install packages via the distro's native package manager (caller
    passes current-distro names). Non-interactive; --needed skips current."""
    from distro import UnsupportedDistroError, package_manager_install_cmd
    try:
        base = package_manager_install_cmd()
    except UnsupportedDistroError as exc:
        fail(str(exc))
        fail(f"install manually: {' '.join(pkgs)}")
        return False
    return _run_pkg_cmd(base, *pkgs)


def pkg_sync_install(*pkgs: str) -> bool:
    """Refresh the package db, then install every package in one shot.
    --needed lets the package manager skip what's already current."""
    from distro import (
        UnsupportedDistroError, package_manager_install_cmd,
        package_manager_sync_cmd,
    )
    try:
        sync = package_manager_sync_cmd()
        install = package_manager_install_cmd()
    except UnsupportedDistroError as exc:
        fail(str(exc))
        fail(f"install manually: {' '.join(pkgs)}")
        return False
    if sync is not None:
        _run_pkg_cmd(sync)
    return _run_pkg_cmd(install, *pkgs)


_QDBUS_CACHE: list[str] | None = None


def qdbus_cmd() -> str | None:
    # Arch/Alpine/Debian/openSUSE ship qdbus6; Fedora/RHEL ship qdbus-qt6;
    # older systems only qdbus (Qt5).
    global _QDBUS_CACHE
    if _QDBUS_CACHE is None:
        _QDBUS_CACHE = [c for c in ("qdbus6", "qdbus-qt6", "qdbus") if have(c)]
    return _QDBUS_CACHE[0] if _QDBUS_CACHE else None


def qdbus_call(*args: str) -> bool:
    """Fire-and-forget qdbus, bounded at 15s so a degraded plasmashell/kwin
    DBus endpoint can't hang the installer (longest legit response ~3s)."""
    q = qdbus_cmd()
    if not q:
        return False
    try:
        return subprocess.run(
            [q, *args], check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=15,
            preexec_fn=drop_privs_in_child,
        ).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def kwin_reconfigure() -> None:
    qdbus_call("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")


# kwriteconfig6's --notify needs a live session bus; without one the call
# fails silently and the write is dropped (TTY/ssh/CI/sandboxed contexts).
_HAS_DBUS: bool | None = None


def _has_session_dbus() -> bool:
    global _HAS_DBUS
    if _HAS_DBUS is not None:
        return _HAS_DBUS
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS") or not have("dbus-send"):
        _HAS_DBUS = False
        return _HAS_DBUS
    try:
        _HAS_DBUS = subprocess.run(
            ["dbus-send", "--session", "--print-reply",
             "--dest=org.freedesktop.DBus", "/org/freedesktop/DBus",
             "org.freedesktop.DBus.ListNames"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=5,
            preexec_fn=drop_privs_in_child,
        ).returncode == 0
    except subprocess.TimeoutExpired:
        _HAS_DBUS = False
    return _HAS_DBUS


def kw_write(*args: str) -> bool:
    if not have("kwriteconfig6"):
        return False
    cmd = ["kwriteconfig6"]
    if _has_session_dbus():
        cmd.append("--notify")
    cmd.extend(args)
    try:
        return subprocess.run(
            cmd, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=5,
            preexec_fn=drop_privs_in_child,
        ).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def kw_read(file: str, group: str, key: str) -> str:
    if not have("kreadconfig6"):
        return ""
    try:
        return subprocess.run(
            ["kreadconfig6", "--file", file, "--group", group, "--key", key],
            check=False, capture_output=True, text=True,
            timeout=5,
            preexec_fn=drop_privs_in_child,
        ).stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


def build_group_args(section: str) -> list[str]:
    """Split nested KDE sections into the ``--group`` chain kwriteconfig wants.

    ``Colors:Header][Inactive`` → ``--group Colors:Header --group Inactive``
    """
    args: list[str] = []
    rest = section
    while True:
        idx = rest.find("][")
        if idx < 0:
            break
        args.extend(["--group", rest[:idx]])
        rest = rest[idx + 2:]
    args.extend(["--group", rest])
    return args


def ensure_dir(p: Path | str) -> Path:
    path = Path(p)
    path.mkdir(parents=True, exist_ok=True)
    return path


def remove_path(p: Path | str) -> None:
    path = Path(p)
    if path.is_symlink() or path.is_file():
        try:
            path.unlink()
        except OSError:
            pass
    elif path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def iter_glob(root: Path | str, patterns: Iterable[str]):
    root = Path(root)
    for pat in patterns:
        yield from root.glob(pat)
