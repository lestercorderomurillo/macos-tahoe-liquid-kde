import json
import os
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Iterable

from log import fail, ok, warn


_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "MacTahoeLiquidKDE/installer"
)


def fetch(url: str, dest: Path | str, referer: str | None = None,
          retries: int = 3) -> bool:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": _USER_AGENT}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    for _ in range(max(1, retries)):
        try:
            with urllib.request.urlopen(req, timeout=60) as r, dest.open("wb") as f:
                shutil.copyfileobj(r, f)
            return True
        except (urllib.error.URLError, OSError, TimeoutError):
            continue
    if dest.exists():
        try:
            dest.unlink()
        except OSError:
            pass
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


def safe_copy(src: Path | str, dest: Path | str) -> bool:
    """Atomic copy via tmp + rename, with rollback on failure.

    ``symlinks=True`` matches GNU ``cp -r`` semantics. Without it the icon
    themes balloon to 2-3x their size — the @2x and dark→light inheritance
    symlinks get dereferenced into full duplicate trees, which also breaks
    the icon-theme lookup for anything resolving via the @2x convention.
    """
    src = Path(src)
    dest = Path(dest)
    parent = dest.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp = parent / f".tmp_{dest.name}_{os.getpid()}"
    bak = parent / f".bak_{dest.name}_{os.getpid()}"

    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    try:
        shutil.copytree(src, tmp, symlinks=True)
    except OSError:
        shutil.rmtree(tmp, ignore_errors=True)
        return False

    try:
        if dest.exists():
            try:
                dest.rename(bak)
            except OSError:
                shutil.rmtree(dest, ignore_errors=True)
        tmp.rename(dest)
    except OSError:
        if bak.exists():
            try:
                bak.rename(dest)
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
    if have("pacman"):
        cmd = ["sudo", "pacman", "-S", "--noconfirm", *pkgs]
    elif have("yay"):
        cmd = ["yay", "-S", "--noconfirm", *pkgs]
    elif have("paru"):
        cmd = ["paru", "-S", "--noconfirm", *pkgs]
    else:
        fail(f"no package manager found — install {' '.join(pkgs)} manually")
        return False
    return subprocess.run(cmd, check=False).returncode == 0


def auto_dep(cmd: str, pkg: str | None = None) -> bool:
    pkg = pkg or cmd
    if have(cmd):
        ok(cmd)
        return True
    warn(f"{cmd} not found — installing...")
    if pkg_install(pkg):
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
    q = qdbus_cmd()
    if not q:
        return False
    return subprocess.run(
        [q, *args], check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


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
    ).returncode == 0


def kw_read(file: str, group: str, key: str) -> str:
    if not have("kreadconfig6"):
        return ""
    return subprocess.run(
        ["kreadconfig6", "--file", file, "--group", group, "--key", key],
        check=False, capture_output=True, text=True,
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
