#!/usr/bin/env python3
"""Internal engine entry point for the GUI and isolated qualification tools."""

import sys
import os
from contextlib import nullcontext
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cli import run_install, run_uninstall
from installer_lock import installer_lock, InstallerBusy


def main(argv):
    if not argv or argv[0] not in ("install", "uninstall"):
        print("Internal backend requires install or uninstall", file=sys.stderr)
        return 2
    try:
        with installer_lock() if os.geteuid() == 0 else nullcontext():
            return (run_install if argv[0] == "install" else run_uninstall)(argv[1:])
    except (ValueError, TypeError, OSError, InstallerBusy) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
