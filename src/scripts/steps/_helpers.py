"""Common helpers shared between step modules."""

import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from paths import BUILD_DIR, LEGACY_STEPS_DIR, OFFLINE_DIR, SRC_DIR, STEPS_DIR
from log import fail, info, ok, reinstall, warn
from utils import have, kw_write, qdbus_call, safe_copy


HOME = Path.home()


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


@contextmanager
def _as_root() -> Iterator[None]:
    """Briefly re-elevate to root for one privileged operation. The CLI
    uninstall entry point demands ``sudo ./uninstall`` (real UID stays 0) and then
    drops the *effective* UID to ``SUDO_USER`` so user-side writes get
    correct ownership. ``seteuid(0)`` is reversible because real UID is
    still 0, so this hop is always safe."""
    saved_euid = os.geteuid()
    saved_egid = os.getegid()
    if saved_euid == 0:
        # Already root (script invoked as the real root login, no drop
        # happened). Just run the body.
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
    """Copy a file to a root-owned destination. The script is already
    root-capable at this point (the CLI bailed early otherwise), so this
    is just an atomic ``copy + rename`` performed under a transient
    ``seteuid(0)`` — no sudo subprocess, no PAM conv, no faillock surface.
    """
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


def sudo_remove(path: Path, label: str | None = None) -> bool:
    label = label or path.name
    if not path.exists() and not path.is_symlink():
        return False
    try:
        with _as_root():
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
    """Self-cleaning ``/tmp/<prefix>-<pid>`` directory."""
    p = Path(f"/tmp/{prefix}-{os.getpid()}")
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)
    p.mkdir(parents=True)
    try:
        yield p
    finally:
        shutil.rmtree(p, ignore_errors=True)


def cmake_build(src_dir_: Path, build_dir: Path, label: str) -> bool:
    if not (src_dir_ / "CMakeLists.txt").is_file():
        warn(f"{label} source not found — skipping")
        return False
    # Wipe stale build dirs. Earlier ``sudo ./install`` runs (before the
    # CLI started dropping privileges) may have left root-owned files
    # under build/. ignore_errors=True would silently skip them and the
    # subsequent mkdir would then trip FileExistsError, which would
    # surface as a confusing "cmake configure failed". Try as user
    # first; if anything's left over, hop to root via _as_root for the
    # cleanup so the new build starts from an empty dir.
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)
        if build_dir.exists():
            with _as_root():
                shutil.rmtree(build_dir, ignore_errors=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    cfg = subprocess.run(
        ["cmake", "-S", str(src_dir_), "-B", str(build_dir),
         "-DCMAKE_BUILD_TYPE=Release"],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if cfg.returncode != 0:
        fail(f"{label}: cmake configure failed")
        return False
    nproc = os.cpu_count() or 1
    mk = subprocess.run(
        ["make", "-C", str(build_dir), f"-j{nproc}"],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if mk.returncode != 0:
        fail(f"{label}: build failed")
        return False
    ok(f"{label} built")
    return True


__all__ = [
    "HOME", "feat_enabled", "theme_mode", "offline", "steps_dir",
    "build_dir",
    "legacy_steps_dir", "src_dir",
    "install_tree", "remove_tree", "sudo_install_file", "sudo_remove",
    "temp_dir", "cmake_build",
    # re-exports for step modules
    "fail", "info", "ok", "reinstall", "warn",
    "have", "kw_write", "qdbus_call",
]
