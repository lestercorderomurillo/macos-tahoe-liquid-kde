import errno
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Iterable

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

    Backoff schedule: 0s before the first attempt, then 1s, 2s, 4s
    before each subsequent retry. The 7s total wall-clock added to a
    full 3-retry failure is cheaper than asking the user to re-run the
    whole installer for a transient network blip."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": _USER_AGENT}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    last_err: str = ""
    for attempt in range(max(1, retries)):
        if attempt > 0:
            time.sleep(2 ** (attempt - 1))  # 1s, 2s, 4s
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


def extract(archive: Path | str, dest: Path | str) -> bool:
    archive = Path(archive)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    name = archive.name.lower()

    if name.endswith(".zip"):
        # Python's zipfile.extractall does not preserve Unix symlinks —
        # it writes them out as 8-byte text files containing the link
        # target. Upstream icon themes (vinceliuice MacTahoe, etc.) ship
        # thousands of alias symlinks, so this manifests as "lots of icons
        # missing" post-install. System `unzip` preserves the symlink
        # mode bits correctly. Fall back to the broken zipfile path only
        # when unzip is unavailable.
        if have("unzip"):
            return subprocess.run(
                ["unzip", "-q", "-o", str(archive), "-d", str(dest)],
                check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            ).returncode == 0
        try:
            with zipfile.ZipFile(archive) as z:
                _extract_zip_with_symlinks(z, dest)
            return True
        except (zipfile.BadZipFile, OSError):
            return False

    try:
        if name.endswith((".tar.gz", ".tgz")):
            mode = "r:gz"
        elif name.endswith(".tar.xz"):
            mode = "r:xz"
        elif name.endswith(".tar.bz2"):
            mode = "r:bz2"
        elif ".tar" in name:
            mode = "r:*"
        else:
            return False
        with tarfile.open(archive, mode) as t:
            t.extractall(dest)
        return True
    except (tarfile.TarError, OSError):
        return False


_ZIP_SYMLINK_MODE = 0o120000


def _extract_zip_with_symlinks(zf: zipfile.ZipFile, dest: Path) -> None:
    """Pure-Python zip extractor that honours the Unix symlink mode bits.

    The ZipInfo.external_attr top 16 bits are the Unix st_mode; a symlink
    has the 0o120000 bits set. zipfile.extractall ignores this and writes
    the link target as plain file content.
    """
    for info in zf.infolist():
        target = dest / info.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        unix_mode = (info.external_attr >> 16) & 0o170000
        if unix_mode == _ZIP_SYMLINK_MODE:
            link_to = zf.read(info).decode("utf-8", errors="replace")
            if target.is_symlink() or target.exists():
                target.unlink()
            target.symlink_to(link_to)
        else:
            zf.extract(info, dest)


def load_mirrors(json_file: Path | str, source_idx: int = 0) -> list[dict]:
    data = json.loads(Path(json_file).read_text())
    return data["sources"][source_idx].get("mirrors", [])


def run_mirrors(json_file: Path | str, source_idx: int, tmp_dir: Path,
                handle: Callable[..., bool]) -> bool:
    """Walk mirrors for one source, calling ``handle`` until one succeeds.

    For ``format: base`` mirrors, ``handle(url, prefix, referer)`` runs
    directly with the upstream URL. Otherwise we download to ``tmp_dir``,
    extract, and call ``handle(extract_dir, prefix)``.
    """
    tmp_dir = Path(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for i, mirror in enumerate(load_mirrors(json_file, source_idx), start=1):
        url = mirror["url"]
        fmt = mirror.get("format", "zip")
        prefix = mirror.get("prefix", "")
        referer = mirror.get("referer", "") or None

        if fmt == "base":
            try:
                done = handle(url, prefix, referer)
            except TypeError:
                done = handle(url, prefix)
            if done:
                ok(f"mirror {i}")
                return True
            continue

        out = tmp_dir / f"mirror{i}.{fmt}"
        xdir = tmp_dir / f"extract{i}"
        if not fetch(url, out, referer):
            continue
        if not extract(out, xdir):
            continue
        if handle(xdir, prefix):
            ok(f"mirror {i}")
            return True
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
    if have(cmd):
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
    global _QDBUS_CACHE
    if _QDBUS_CACHE is None:
        _QDBUS_CACHE = [c for c in ("qdbus6", "qdbus") if have(c)]
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
