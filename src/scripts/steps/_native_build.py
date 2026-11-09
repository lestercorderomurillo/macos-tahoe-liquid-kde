"""Native compilation helpers, separate from payload copying and icon generation.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import os
import shutil
import subprocess
from pathlib import Path

from component_cache import identity
from component_manifest import dependencies
from localization import tr
from log import fail, ok, warn
from steps._helpers import _as_root, _drop_privs_in_child


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
    # Source identity, not checkout timestamps, decides whether this component
    # may reuse its build graph. CMake and Make still check the current SDK.
    scripts = Path(__file__).resolve().parent.parent
    recipe = dependencies(Path(__file__), scripts)
    source_key = identity(
        [("source", src_dir_)] + [(str(path.relative_to(scripts)), path) for path in recipe],
        list(targets),
    )
    stamp = build_dir / ".mttkde-source-sha256"
    cache = build_dir / "CMakeCache.txt"
    reusable = False
    try:
        reusable = (stamp.read_text() == source_key and
                    f"CMAKE_HOME_DIRECTORY:INTERNAL={src_dir_.resolve()}" in cache.read_text().splitlines()
                    and os.access(build_dir, os.W_OK, effective_ids=True))
    except OSError:
        pass
    if build_dir.exists() and not reusable:
        shutil.rmtree(build_dir, ignore_errors=True)
        if build_dir.exists():
            with _as_root():
                shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    stamp.unlink(missing_ok=True)
    # Reuse compiler results even when an archive forces a fresh build graph.
    # Explicit environment or cached launchers (including an empty value) win.
    launchers = []
    try:
        cache_lines = cache.read_text().splitlines()
    except OSError:
        cache_lines = []
    compiler_cache = shutil.which("ccache")
    if compiler_cache:
        for language in ("C", "CXX"):
            variable = f"CMAKE_{language}_COMPILER_LAUNCHER"
            if variable not in os.environ and not any(
                line.startswith(variable + ":") for line in cache_lines
            ):
                launchers.append(f"-D{variable}={compiler_cache}")
    cfg = subprocess.run(
        ["cmake", "-S", str(src_dir_), "-B", str(build_dir),
         "-DCMAKE_BUILD_TYPE=Release",
         # compile_commands.json lets clangd resolve Qt AUTOMOC headers.
         "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON", *launchers],
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
    stamp.write_text(source_key)
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


