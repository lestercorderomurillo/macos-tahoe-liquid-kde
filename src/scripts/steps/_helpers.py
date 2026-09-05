"""Common helpers shared between step modules."""

import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from paths import BUILD_DIR, LEGACY_STEPS_DIR, OFFLINE_DIR, SRC_DIR, STEPS_DIR
from log import fail, info, ok, reinstall, warn
from utils import drop_privs_in_child, have, kw_write, qdbus_call, safe_copy


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
    label = label or dest.name
    if not src.is_dir():
        fail(f"{label} (source missing: {src})")
        return False
    existed = dest.is_dir()
    if not safe_copy(src, dest):
        fail(f"{label} (copy failed)")
        return False
    if existed:
        reinstall(label)
    else:
        ok(f"{label} (installed)")
    return True


def remove_tree(p: Path, label: str | None = None) -> bool:
    label = label or p.name
    if not p.exists():
        return False
    try:
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        else:
            p.unlink()
        ok(f"{label} removed")
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


def sudo_install_file(src: Path, dest: Path, label: str) -> bool:
    """Atomic copy+rename to a root-owned destination under a transient
    seteuid(0) — no sudo subprocess, no PAM conv, no faillock surface."""
    src = Path(src)
    dest = Path(dest)
    try:
        with _as_root():
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".mttkde-tmp")
            shutil.copy2(str(src), str(tmp))
            os.replace(str(tmp), str(dest))
    except OSError as exc:
        fail(f"{label} ({exc.__class__.__name__}: {exc})")
        return False
    ok(label)
    return True


def sudo_install_tree(src: Path, dest: Path, label: str | None = None) -> bool:
    """Copy a tree to a root-owned destination, staged at a sibling
    .mttkde-tmp then renamed so the live destination is never half-written."""
    label = label or dest.name
    src = Path(src)
    dest = Path(dest)
    if not src.is_dir():
        fail(f"{label} (source missing: {src})")
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
    label = label or path.name
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
    if not (src_dir_ / "CMakeLists.txt").is_file():
        warn(f"{label} source not found — skipping")
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
        fail(f"{label}: cmake configure failed")
        _emit_cmd_log(label, "cmake", cfg.stdout, cfg.stderr, build_dir / "cmake-configure.log")
        return False
    nproc = os.cpu_count() or 1
    mk = subprocess.run(
        ["make", "-C", str(build_dir), f"-j{nproc}", *targets],
        check=False, capture_output=True, text=True,
        preexec_fn=_drop_privs_in_child,
    )
    if mk.returncode != 0:
        fail(f"{label}: build failed")
        _emit_cmd_log(label, "make", mk.stdout, mk.stderr, build_dir / "make-build.log")
        return False
    ok(f"{label} built")
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
        print(f"     \033[2m── {tool} output (tail) ──\033[0m")
        for line in tail:
            print(f"     \033[2m{line}\033[0m")
    if log_path:
        print(f"     \033[2mfull log: {log_path}\033[0m")


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
