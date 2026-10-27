#!/usr/bin/env python3
"""Internal engine entry point for the GUI and isolated qualification tools."""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cli import run_install, run_uninstall


def main(argv):
    if not argv or argv[0] not in ("install", "uninstall"):
        print("Internal backend requires install or uninstall", file=sys.stderr)
        return 2
    try:
        return (run_install if argv[0] == "install" else run_uninstall)(argv[1:])
    except (ValueError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
