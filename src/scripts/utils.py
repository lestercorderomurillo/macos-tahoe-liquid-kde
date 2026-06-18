import errno
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

from log import fail, ok, warn


def drop_privs_in_child() -> None:
    """``preexec_fn`` for subprocess: in the forked child, fully drop
    real+effective+saved UID/GID to ``SUDO_USER`` before ``exec()``.

    Mandatory for Qt6 binaries (qtpaths, qmake6, kwriteconfig6, qdbus6,
    kreadconfig6, …). Qt6 ``QCoreApplication`` startup checks
    ``getuid() != geteuid()`` — when true, it prints ``FATAL: The
    application binary appears to be running setuid`` and aborts.

    The CLI privilege-drop leaves the parent at real-UID 0 / effective-
    UID user (intentional, so the few /usr/lib writes can hop back to
    root via ``_as_root()``). Forked children inherit that mismatch and
    every Qt6 binary refuses to run, which is why kwriteconfig6 has
    been silently no-op'ing the theme writes — the post-install
    verification reads back empty across the board.

    ``setresuid(uid, uid, uid)`` is allowed for an unprivileged process
    when each new value is one of the current real / effective / saved
    UIDs. We pass ``uid == old effective UID``, so every slot gets a
    valid value — permitted without CAP_SETUID. The child can never
    re-elevate; the parent (real UID still 0) keeps its hop-back."""
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
    """``subprocess.run`` wrapper that fully drops privileges in the
    child before exec via ``drop_privs_in_child``. Use for every
    subprocess that runs a Qt6 / KDE binary or anything else that
    should execute under the invoking user's identity (kwriteconfig6,
    kpackagetool6, plasma-apply-*, kvantummanager, kbuildsycoca6, etc.).

    Skip this helper only when the child *needs* root (``sudo`` itself
    in pkg_install, or commands that write under ``/usr`` from the
    child — there are none of those today; ``/usr`` writes go through
    ``_as_root()`` in the parent)."""
    if "preexec_fn" not in kwargs:
        kwargs["preexec_fn"] = drop_privs_in_child
    return subprocess.run(*args, **kwargs)


_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "MacTahoeLiquidKDE/installer"
)


# Hard ceiling so a caller can never request unbounded retries. With
# the default 60s socket timeout per attempt + the 0/1/2/4/8s backoff
# schedule, MAX_FETCH_RETRIES=5 caps a single fetch at ~5 min worst-
# case (60×5 + 1+2+4+8). Anything more than that and the user is
# better served by failing fast and surfacing the error.
MAX_FETCH_RETRIES = 5


def fetch(url: str, dest: Path | str, referer: str | None = None,
          retries: int = 3) -> bool:
    """Download ``url`` to ``dest`` with exponential backoff between
    attempts and Content-Length validation.

    Returns True only when the full byte count promised by the server
    actually landed on disk. A truncated download (server hung up
    mid-stream without raising an exception — common on flaky CDN
    edges) was previously silently treated as success; the wallpaper
    step would then ``fail`` later with ``download incomplete — re-run
    to retry`` because the on-disk file was empty / partial. We now
    detect that here and retry with backoff.

    Backoff schedule: 0s before the first attempt, then 1s, 2s, 4s, 8s
    before each subsequent retry. ``retries`` is clamped to
    ``[1, MAX_FETCH_RETRIES]`` so a caller can never request unbounded
    work. On final failure the partial file is deleted (no half-baked
    artefacts left behind) and an error line goes to stderr."""
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
            time.sleep(2 ** (attempt - 1))  # 1s, 2s, 4s, 8s
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                expected = r.headers.get("Content-Length")
                expected_n = int(expected) if expected and expected.isdigit() else None
                with dest.open("wb") as f:
                    shutil.copyfileobj(r, f)
            # Validate full body landed. Servers that omit Content-Length
            # (chunked transfer, gzip-on-the-fly) just skip this check —
            # we have no ground truth for those.
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
    """Resolve the staging dir lazily on every call. Eager evaluation at
    module import bit us when the CLI used to invoke ``sudo ./install`` and
    later drops privileges to ``SUDO_USER``: at import time HOME was
    still ``/root``, so the cached path was ``/root/.cache/...`` and
    every later ``safe_copy`` blew up with ``PermissionError`` once we
    were no longer root."""
    cache_home = (
        os.environ.get("XDG_CACHE_HOME")
        or os.path.expanduser("~/.cache")
    )
    return Path(cache_home) / "mac-tahoe-liquid-kde-staging"


def safe_copy(src: Path | str, dest: Path | str) -> bool:
    """Atomic copy via staging dir + rename, with rollback on failure.

    ``symlinks=True`` matches GNU ``cp -r`` semantics. Without it the icon
    themes balloon to 2-3x their size — the @2x and dark→light inheritance
    symlinks get dereferenced into full duplicate trees, which also breaks
    the icon-theme lookup for anything resolving via the @2x convention.

    Staging dir lives outside ``dest.parent`` because ``~/.local/share/wallpapers``
    is watched live by plasmashell's KDirWatch. If we wrote ``.tmp_*`` /
    ``.bak_*`` siblings of the final destination, plasmashell would scan
    them mid-copy and crash inside ``libplasma_wallpaper_image.so`` trying
    to load half-built packages. By staging in ``~/.cache/`` and moving the
    fully-formed tree across only at the end, KDirWatch only ever sees
    complete wallpaper packages.

    Cross-filesystem ``Path.rename`` on Linux falls back to copy+unlink
    (``EXDEV``); we catch that and use ``shutil.move``, which handles it
    transparently. Same FS is the common case (cache and share both under
    ``$HOME``)."""
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


# Env vars that a live Plasma session exports. Any one of them is a
# positive signal — but they are NOT load-bearing: ``sudo`` strips the
# session environment, and the CLI's ``_restore_user_session_env`` only
# recovers a subset, so an empty environment here means "couldn't tell",
# not "not Plasma". See is_plasma_session() for why the binary wins.
_PLASMA_SESSION_ENV = (
    ("XDG_CURRENT_DESKTOP", "KDE"),
    ("XDG_SESSION_DESKTOP", "plasma"),
    ("KDE_FULL_SESSION", None),
    ("KDE_SESSION_VERSION", None),
)


def is_plasma_session() -> bool:
    """Single source of truth for "is this a KDE Plasma host?".

    This installer hard-requires ``plasmashell`` at the preflight gate
    (``verify_plasma``), so the presence of the binary is the canonical,
    sudo-proof signal — it survives the environment stripping that
    ``sudo`` performs, which the session env vars do not. We anchor on
    the binary and treat the session env vars only as a corroborating
    positive: if either says "yes", it's Plasma.

    Previously the Nautilus step kept its own ``_is_kde()`` that read the
    env vars *alone*; under ``sudo`` those came back empty and it falsely
    reported "Not running under KDE Plasma" even though preflight had
    just confirmed Plasma from the binary. Reusing one helper keeps the
    two checks from ever disagreeing again.
    """
    if have("plasmashell"):
        return True
    for name, expected in _PLASMA_SESSION_ENV:
        value = os.environ.get(name, "")
        if not value:
            continue
        if expected is None or expected in value:
            return True
    return False


def _cmake_package_exists(name: str) -> bool:
    if not have("cmake"):
        return False
    try:
        with tempfile.TemporaryDirectory(prefix="mttkde-cmake-probe-") as tmp:
            src = Path(tmp) / "src"
            build = Path(tmp) / "build"
            src.mkdir(parents=True, exist_ok=True)
            (src / "CMakeLists.txt").write_text(
                "\n".join((
                    "cmake_minimum_required(VERSION 3.16)",
                    "project(mttkde_dep_probe LANGUAGES CXX)",
                    f"find_package({name} CONFIG QUIET)",
                    f"if(NOT {name}_FOUND)",
                    f'  message(FATAL_ERROR "{name} not found")',
                    "endif()",
                    "",
                )),
                encoding="utf-8",
            )
            res = run_user(
                [
                    "cmake",
                    "-S", str(src),
                    "-B", str(build),
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return res.returncode == 0


# deps() tokens that map to a cmake config package rather than a
# binary on PATH. The value is the ``<Name>`` we pass to
# ``find_package(<Name> CONFIG)`` — same string the failing CMakeLists
# uses, so a missing-dep failure in preflight names exactly what cmake
# would have complained about.
_CMAKE_PACKAGE_TOKENS: dict[str, str] = {
    "ecm":                            "ECM",
    "qt6-gui-cmake":                  "Qt6Gui",
    "qt6-widgets-cmake":              "Qt6Widgets",
    "qt6-dbus-cmake":                 "Qt6DBus",
    "qt6-qml-cmake":                  "Qt6Qml",
    "qt6-uitools-cmake":              "Qt6UiTools",
    # KF6 frameworks required by the compiled plasmoids + acrylic-glass.
    "kf6-config-cmake":               "KF6Config",
    "kf6-configwidgets-cmake":        "KF6ConfigWidgets",
    "kf6-coreaddons-cmake":           "KF6CoreAddons",
    "kf6-crash-cmake":                "KF6Crash",
    "kf6-globalaccel-cmake":          "KF6GlobalAccel",
    "kf6-guiaddons-cmake":            "KF6GuiAddons",
    "kf6-i18n-cmake":                 "KF6I18n",
    "kf6-kcmutils-cmake":             "KF6KCMUtils",
    "kf6-kio-cmake":                  "KF6KIO",
    "kf6-notifications-cmake":        "KF6Notifications",
    "kf6-service-cmake":              "KF6Service",
    "kf6-widgetsaddons-cmake":        "KF6WidgetsAddons",
    "kf6-windowsystem-cmake":         "KF6WindowSystem",
    "kf6-itemmodels-cmake":           "KF6ItemModels",
    # Plasma / KSysGuard / plasma-workspace cmake configs.
    "plasma-cmake":                   "Plasma",
    "plasma-activities-cmake":        "PlasmaActivities",
    "plasma-activities-stats-cmake":  "PlasmaActivitiesStats",
    "ksysguard-cmake":                "KSysGuard",
    "libnotificationmanager-cmake":   "LibNotificationManager",
    "libtaskmanager-cmake":           "LibTaskManager",
    # KWin (Wayland) + KDecoration3 for the acrylic-glass effect.
    "kwin-cmake":                     "KWin",
    "kdecoration-cmake":              "KDecoration3",
    # libepoxy / X11 / XCB are probed via pkg-config instead — see
    # _PKGCONFIG_TOKENS below.
}


def _pkgconfig_available(name: str) -> bool:
    """``pkg-config --exists`` probe. Used for X11 / XCB / epoxy where
    the cmake module ships outside the package's own tree (ECM
    FindXCB.cmake, /usr/share/cmake/Modules/FindX11.cmake) and a CONFIG
    package probe would fail even though the dev files are installed.
    """
    if not have("pkg-config"):
        return False
    try:
        res = run_user(
            ["pkg-config", "--exists", name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return res.returncode == 0


# Tokens that should be probed via pkg-config rather than
# ``find_package(... CONFIG)`` — see :func:`_pkgconfig_available`.
_PKGCONFIG_TOKENS: dict[str, str] = {
    "epoxy-cmake": "epoxy",
    "x11-cmake":   "x11",
    "xcb-cmake":   "xcb",
}


def _dep_available(cmd: str) -> bool:
    pc_name = _PKGCONFIG_TOKENS.get(cmd)
    if pc_name is not None:
        return _pkgconfig_available(pc_name)
    cmake_name = _CMAKE_PACKAGE_TOKENS.get(cmd)
    if cmake_name is not None:
        return _cmake_package_exists(cmake_name)
    # The ``qdbus6`` token names a binary whose on-PATH name varies per
    # distro (Fedora/RHEL ship it as ``qdbus-qt6``, Qt5-only systems as
    # ``qdbus``). A literal ``have("qdbus6")`` therefore reports "not
    # found" on Fedora even when the tool is installed, so auto_dep() ran
    # a noisy no-op reinstall every run. Reuse the same multi-name
    # resolver the runtime callers use so detection and invocation agree.
    if cmd == "qdbus6":
        return qdbus_cmd() is not None
    return have(cmd)


def pkg_install(*pkgs: str) -> bool:
    """Install one or more packages via the distro's native package
    manager (resolved through :mod:`distro`). The caller passes the
    *current-distro* package names — use :func:`auto_dep` if the
    deps() token still needs translating."""
    from distro import UnsupportedDistroError, package_manager_install_cmd
    try:
        base = package_manager_install_cmd()
    except UnsupportedDistroError as exc:
        fail(str(exc))
        fail(f"install manually: {' '.join(pkgs)}")
        return False
    # Prepend sudo when we're not already running as root.
    cmd = base if os.geteuid() == 0 else ["sudo", *base]
    cmd.extend(pkgs)
    return subprocess.run(cmd, check=False).returncode == 0


def auto_dep(cmd: str, pkg: str | None = None) -> bool:
    """Ensure ``cmd`` resolves on PATH, installing the per-distro
    package if it doesn't. ``pkg`` is the Arch-flavoured package name
    from the step's deps() token — distro.package_for() translates it
    to the right name on the current host."""
    from distro import package_for
    if _dep_available(cmd):
        ok(cmd)
        return True
    warn(f"{cmd} not found — installing...")
    if pkg_install(package_for(cmd, pkg)):
        ok(f"{cmd} (installed)")
        return True
    fail(f"{cmd} (install failed)")
    return False


_QDBUS_CACHE: list[str] | None = None


def qdbus_cmd() -> str | None:
    # Binary name varies per distro: Arch / Alpine / Debian / openSUSE
    # ship ``qdbus6`` on PATH; Fedora and RHEL ship the same tool as
    # ``qdbus-qt6``; older systems expose only ``qdbus`` (Qt5). Check
    # all three in preference order.
    global _QDBUS_CACHE
    if _QDBUS_CACHE is None:
        _QDBUS_CACHE = [c for c in ("qdbus6", "qdbus-qt6", "qdbus") if have(c)]
    return _QDBUS_CACHE[0] if _QDBUS_CACHE else None


def qdbus_call(*args: str) -> bool:
    """Fire-and-forget qdbus invocation. Bounded by a 15s timeout so a
    degraded plasmashell / kwin DBus endpoint can never hang the
    installer indefinitely — the longest legitimate response we've seen
    is ~3s for ``KWin.reconfigure`` on a slow machine."""
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
    _HAS_DBUS = subprocess.run(
        ["dbus-send", "--session", "--print-reply",
         "--dest=org.freedesktop.DBus", "/org/freedesktop/DBus",
         "org.freedesktop.DBus.ListNames"],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        preexec_fn=drop_privs_in_child,
    ).returncode == 0
    return _HAS_DBUS


def kw_write(*args: str) -> bool:
    if not have("kwriteconfig6"):
        return False
    cmd = ["kwriteconfig6"]
    if _has_session_dbus():
        cmd.append("--notify")
    cmd.extend(args)
    return subprocess.run(
        cmd, check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        preexec_fn=drop_privs_in_child,
    ).returncode == 0


def kw_read(file: str, group: str, key: str) -> str:
    if not have("kreadconfig6"):
        return ""
    return subprocess.run(
        ["kreadconfig6", "--file", file, "--group", group, "--key", key],
        check=False, capture_output=True, text=True,
        preexec_fn=drop_privs_in_child,
    ).stdout.strip()


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
