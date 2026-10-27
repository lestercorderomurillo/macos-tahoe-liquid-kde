"""Common helpers shared between step modules."""

from localization import tr

import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from paths import BUILD_DIR, LEGACY_STEPS_DIR, OFFLINE_DIR, SRC_DIR, STEPS_DIR
from log import fail, info, ok, reinstall, warn
from utils import (
    drop_privs_in_child, have, kw_write, qdbus_call, qdbus_cmd, run_user, safe_copy,
)


HOME = Path.home()
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME") or HOME / ".local/share")


def feat_enabled(name: str, default: bool = True) -> bool:
    val = os.environ.get(f"FEAT_{name.upper()}")
    if val is None:
        return default
    return val.lower() == "true"


def theme_mode() -> str:
    return os.environ.get("THEME_MODE", "auto")


def offline(*parts: str) -> Path:
    return Path(os.environ.get("OFFLINE", str(OFFLINE_DIR)), *parts)


def steps_dir(*parts: str) -> Path:
    return Path(os.environ.get("STEPS", str(STEPS_DIR)), *parts)


def build_dir(*parts: str) -> Path:
    return Path(os.environ.get("BUILD", str(BUILD_DIR)), *parts)


def legacy_steps_dir(*parts: str) -> Path:
    return Path(str(LEGACY_STEPS_DIR), *parts)


def src_dir(*parts: str) -> Path:
    return Path(os.environ.get("SRC", str(SRC_DIR)), *parts)


def install_tree(src: Path, dest: Path, label: str | None = None) -> bool:
    """Copy a directory tree atomically, reporting via ok()/reinstall()/fail()."""
    label = tr(label or dest.name)
    if not src.is_dir():
        fail(tr('{label} (source missing: {src})', label=label, src=src))
        return False
    existed = dest.is_dir()
    if not safe_copy(src, dest):
        fail(tr('{label} (copy failed)', label=label))
        return False
    if existed:
        reinstall(label)
    else:
        ok(tr('{label} (installed)', label=label))
    return True


def remove_tree(p: Path, label: str | None = None) -> bool:
    label = tr(label or p.name)
    if not p.exists():
        return False
    try:
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        else:
            p.unlink()
        ok(tr('{label} removed', label=label))
        return True
    except OSError as exc:
        fail(f"{label}: {exc}")
        return False


# Re-export for step modules still importing drop_privs_in_child from here.
_drop_privs_in_child = drop_privs_in_child


@contextmanager
def _as_root() -> Iterator[None]:
    """Briefly re-elevate to root: the CLI only drops the *effective* UID
    (real UID stays 0), so seteuid(0) is always reversible."""
    saved_euid = os.geteuid()
    saved_egid = os.getegid()
    if saved_euid == 0:
        yield
        return
    try:
        os.seteuid(0)
        os.setegid(0)
        yield
    finally:
        os.setegid(saved_egid)
        os.seteuid(saved_euid)


def sudo_install_file(src: Path, dest: Path, label: str, *, user_owned: bool = False) -> bool:
    """Atomic copy+rename under a transient seteuid(0).

    Destinations default to root ownership. For per-user configuration,
    user_owned keeps the invoking effective UID/GID on the staged file and
    creates its parent directories before elevation.
    """
    label = tr(label)
    src = Path(src)
    dest = Path(dest)
    try:
        owner = (os.geteuid(), os.getegid()) if user_owned else None
        if user_owned:
            # Create per-user directories before elevation so the user can
            # keep managing other files in the same configuration directory.
            dest.parent.mkdir(parents=True, exist_ok=True)
        with _as_root():
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".mttkde-tmp")
            shutil.copy2(str(src), str(tmp))
            if owner is not None:
                os.chown(tmp, *owner, follow_symlinks=False)
            os.replace(str(tmp), str(dest))
    except OSError as exc:
        fail(f"{label} ({exc.__class__.__name__}: {exc})")
        return False
    ok(label)
    return True


def sudo_install_tree(src: Path, dest: Path, label: str | None = None) -> bool:
    """Copy a tree to a root-owned destination, staged at a sibling
    .mttkde-tmp then renamed so the live destination is never half-written."""
    label = tr(label or dest.name)
    src = Path(src)
    dest = Path(dest)
    if not src.is_dir():
        fail(tr('{label} (source missing: {src})', label=label, src=src))
        return False
    try:
        with _as_root():
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".mttkde-tmp")
            if tmp.exists():
                shutil.rmtree(str(tmp))
            shutil.copytree(str(src), str(tmp), symlinks=True)
            if dest.exists():
                shutil.rmtree(str(dest))
            os.replace(str(tmp), str(dest))
    except OSError as exc:
        fail(f"{label} ({exc.__class__.__name__}: {exc})")
        return False
    ok(label)
    return True


def sudo_remove(path: Path, label: str | None = None) -> bool:
    label = tr(label or path.name)
    if not path.exists() and not path.is_symlink():
        return False
    try:
        with _as_root():
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(str(path))
            else:
                path.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        fail(f"{label} ({exc.__class__.__name__}: {exc})")
        return False
    ok(label)
    return True


def kwin_plugin_mapping_matches(maps: str, plugin: Path) -> bool | None:
    """Whether every mapping of ``plugin`` in ``maps`` is the installed file.
    None when the library is not mapped at all."""
    installed = plugin.stat()
    matches = []
    for line in maps.splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) != 6 or fields[5].removesuffix(" (deleted)") != str(plugin):
            continue
        # Btrfs subvolume stat devices can differ from /proc/maps devices.
        # The exact path plus inode identifies the installed file.
        matches.append(int(fields[4]) == installed.st_ino
                       and not fields[5].endswith(" (deleted)"))
    return all(matches) if matches else None


def running_kwin_plugin_matches(plugin: Path) -> bool | None:
    """Check the running KWin's mappings: Qt keeps a replaced plugin library
    resident after its effect instance is reloaded. None when unknown."""
    q = qdbus_cmd()
    if not q:
        return None
    try:
        result = run_user(
            [q, "org.freedesktop.DBus", "/org/freedesktop/DBus",
             "org.freedesktop.DBus.GetConnectionUnixProcessID", "org.kde.KWin"],
            check=False, capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        pid = int(result.stdout.strip())
        if pid <= 0:
            return None
        # KWin's capabilities can deny same-user access to its mappings.
        with _as_root():
            maps = Path(f"/proc/{pid}/maps").read_text()
        return kwin_plugin_mapping_matches(maps, plugin)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


@contextmanager
def temp_dir(prefix: str) -> Iterator[Path]:
    """Self-cleaning, uniquely-named temp directory under /tmp.

    mkdtemp creates it atomically with a random suffix and 0700 perms,
    so a pre-existing file/symlink left at a guessable ``prefix-pid``
    path (stale run under a recycled PID, or planted by another local
    user) can't make this raise instead of failing cleanly, or resolve
    into an attacker-controlled location.
    """
    p = Path(tempfile.mkdtemp(prefix=f"{prefix}-"))
    try:
        yield p
    finally:
        shutil.rmtree(p, ignore_errors=True)


def cmake_build(
    src_dir_: Path,
    build_dir: Path,
    label: str,
    *,
    targets: tuple[str, ...] = (),
) -> bool:
    label = tr(label)
    if not (src_dir_ / "CMakeLists.txt").is_file():
        warn(tr('{label} source not found — skipping', label=label))
        return False
    # Root-owned leftovers from old sudo installs survive the user-level
    # rmtree; retry the wipe as root so mkdir doesn't hit FileExistsError.
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)
        if build_dir.exists():
            with _as_root():
                shutil.rmtree(build_dir, ignore_errors=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    cfg = subprocess.run(
        ["cmake", "-S", str(src_dir_), "-B", str(build_dir),
         "-DCMAKE_BUILD_TYPE=Release",
         # compile_commands.json lets clangd resolve Qt AUTOMOC headers.
         "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"],
        check=False, capture_output=True, text=True,
        preexec_fn=_drop_privs_in_child,
    )
    if cfg.returncode != 0:
        fail(tr('{label}: cmake configure failed', label=label))
        _emit_cmd_log(label, "cmake", cfg.stdout, cfg.stderr, build_dir / "cmake-configure.log")
        return False
    nproc = os.cpu_count() or 1
    mk = subprocess.run(
        ["make", "-C", str(build_dir), f"-j{nproc}", *targets],
        check=False, capture_output=True, text=True,
        preexec_fn=_drop_privs_in_child,
    )
    if mk.returncode != 0:
        fail(tr('{label}: build failed', label=label))
        _emit_cmd_log(label, "make", mk.stdout, mk.stderr, build_dir / "make-build.log")
        return False
    ok(tr('{label} built', label=label))
    return True


def _emit_cmd_log(label: str, tool: str, stdout: str, stderr: str, log_path: Path) -> None:
    """Print the output tail (the last ~25 lines carry the actual
    find_package()/header error) and persist the full log to disk."""
    blob = (stdout or "") + (stderr or "")
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(blob)
    except OSError:
        log_path = None  # type: ignore[assignment]
    tail = [line for line in blob.splitlines() if line.strip()][-25:]
    if tail:
        print(tr('     \x1b[2m── {tool} output (tail) ──\x1b[0m', tool=tool))
        for line in tail:
            print(f"     \033[2m{line}\033[0m")
    if log_path:
        print(tr('     \x1b[2mfull log: {log_path}\x1b[0m', log_path=log_path))


__all__ = [
    "HOME", "DATA_HOME", "feat_enabled", "theme_mode", "offline", "steps_dir",
    "build_dir",
    "legacy_steps_dir", "src_dir",
    "install_tree", "remove_tree", "sudo_install_file", "sudo_install_tree",
    "sudo_remove",
    "temp_dir", "cmake_build",
    # re-exports for step modules
    "fail", "info", "ok", "reinstall", "warn",
    "have", "kw_write", "qdbus_call",
]
