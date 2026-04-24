"""Common helpers shared between step modules."""

import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from paths import OFFLINE_DIR, STEPS_DIR
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


def src_dir(*parts: str) -> Path:
    return Path(os.environ.get("SRC", str(STEPS_DIR.parent)), *parts)


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


def sudo_install_file(src: Path, dest: Path, label: str) -> bool:
    """``sudo cp`` with atomic .tmp → mv. Returns False if either step fails."""
    tmp = f"{dest}.tmp"
    if subprocess.run(["sudo", "cp", str(src), tmp], check=False).returncode != 0:
        fail(f"{label} (sudo cp failed)")
        return False
    if subprocess.run(["sudo", "mv", "-f", tmp, str(dest)], check=False).returncode != 0:
        fail(f"{label} (sudo mv failed)")
        return False
    ok(label)
    return True


def sudo_remove(path: Path, label: str | None = None) -> bool:
    label = label or path.name
    if not path.exists():
        return False
    rc = subprocess.run(["sudo", "rm", "-f", str(path)],
                        check=False).returncode
    if rc == 0:
        ok(label)
        return True
    fail(f"{label} (sudo rm failed)")
    return False


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
    shutil.rmtree(build_dir, ignore_errors=True)
    build_dir.mkdir(parents=True)
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
    "HOME", "feat_enabled", "theme_mode", "offline", "steps_dir", "src_dir",
    "install_tree", "remove_tree", "sudo_install_file", "sudo_remove",
    "temp_dir", "cmake_build",
    # re-exports for step modules
    "fail", "info", "ok", "reinstall", "warn",
    "have", "kw_write", "qdbus_call",
]
