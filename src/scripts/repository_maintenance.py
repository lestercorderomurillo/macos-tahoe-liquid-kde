"""Space maintenance without discarding source history or recovery objects.

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
from pathlib import Path
import subprocess
import sys


def disk_usage(directory: Path) -> int:
    """Allocated bytes, without following symlinks or counting hardlinks twice."""
    seen = set()
    total = 0
    for parent, directories, files in os.walk(directory, followlinks=False):
        for name in directories + files:
            info = (Path(parent) / name).lstat()
            identity = (info.st_dev, info.st_ino)
            if identity not in seen:
                seen.add(identity)
                total += info.st_blocks * 512
    return total


def compact_repository(repository: Path, *, automatic: bool = False) -> dict:
    """Let Git repack its objects; never expire reflogs, prune or change refs.

    Automatic maintenance uses Git's own thresholds. Explicit maintenance
    forces a normal repack, without the CPU/memory cost of --aggressive.
    Linked worktrees and object stores shared with another clone are skipped.
    """
    repository = Path(repository).resolve()
    result = {"repository": str(repository), "status": "skipped", "reclaimed_bytes": 0}
    git_dir = repository / ".git"
    if git_dir.is_symlink() or not git_dir.is_dir():
        result["reason"] = "No independent Git checkout (archives need no Git cleanup)."
        return result
    if ((git_dir / "objects/info/alternates").exists()
            or (git_dir / "worktrees").exists()):
        result["reason"] = "Shared object store or linked worktrees; leaving it unchanged."
        return result
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("GIT_")}
    command = ["git", "-C", str(repository)]
    try:
        top = subprocess.run(command + ["rev-parse", "--show-toplevel"],
                             env=env, capture_output=True, text=True, timeout=15)
        if top.returncode or Path(top.stdout.strip()).resolve() != repository:
            result["reason"] = "Not the root of a Git checkout."
            return result
        before = disk_usage(git_dir) if not automatic else 0
        # Explicit settings override even a user's prune=now or expire=now.
        # Disable detached GC so completion and reported space are truthful.
        operation = subprocess.run(command + [
            "-c", "gc.reflogExpire=never", "-c", "gc.reflogExpireUnreachable=never",
            "-c", "gc.pruneExpire=never", "-c", "gc.worktreePruneExpire=never",
            "-c", "gc.autoDetach=false", "-c", "core.hooksPath=/dev/null",
            "gc", "--no-prune", *(["--auto"] if automatic else []),
        ], env=env, capture_output=True, text=True, timeout=600)
        if operation.returncode:
            result.update(status="failed", reason=operation.stderr.strip())
            return result
        result["status"] = "ok"
        if not automatic:
            after = disk_usage(git_dir)
            result.update(before_bytes=before, after_bytes=after,
                          reclaimed_bytes=max(0, before - after))
    except (OSError, subprocess.SubprocessError) as exc:
        result.update(status="failed", reason=str(exc))
    return result


def main(argv=None) -> int:
    import argparse
    from localization import tr
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "src/installer"))
    from installer_ui import drop_root_to_invoking_user
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", action="append", type=Path)
    parser.add_argument("--auto", action="store_true")
    args = parser.parse_args(argv)
    rc = drop_root_to_invoking_user()
    if rc:
        return rc
    failed = False
    for repository in dict.fromkeys(path.resolve() for path in args.repository or [root]):
        if not args.auto:
            print(tr('Compacting Git storage: {path}', path=repository), flush=True)
        result = compact_repository(repository, automatic=args.auto)
        if result["status"] == "failed":
            failed = True
            print(f'{repository}: {result["reason"]}', file=sys.stderr)
        elif not args.auto:
            if result["status"] == "skipped":
                print(tr(result["reason"]))
            else:
                print(tr('Recovered {size} MiB. Git history and recovery data were preserved.',
                         size=f'{result["reclaimed_bytes"] / 1024**2:.1f}'))
    if not args.auto:
        print(tr('Files still referenced by Git history remain; cleanup does not remove older commits.'))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
