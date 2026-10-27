#!/usr/bin/env python3
"""Read-only desktop qualification probe, run as the guest's desktop user."""
from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src/scripts"))


def require_guest() -> None:
    vendor = Path("/sys/class/dmi/id/sys_vendor").read_text().strip()
    if vendor != "QEMU":
        raise RuntimeError(f"Expected disposable QEMU guest, found {vendor!r}")
    if os.geteuid() == 0:
        raise RuntimeError("Run the desktop probe as the logged-in guest user")


def run(*argv: str) -> str:
    result = subprocess.run(argv, check=True, capture_output=True, text=True, timeout=20)
    return result.stdout.strip()


def verify_panels(panels: list[dict], installed: bool) -> None:
    widgets = {widget for panel in panels for widget in panel["widgets"]}
    if installed:
        required = {
            "org.kde.mac-tahoe-liquid-kde.launcher",
            "org.kde.mac-tahoe-liquid-kde.trashcan",
            "org.kde.mac.tahoe.liquid.icontasks",
            "org.kde.mac.tahoe.liquid.globalmenu",
        }
        if len(panels) < 2 or not required <= widgets:
            raise RuntimeError(f"Missing themed panels/widgets: {sorted(required - widgets)}")
        docks = [panel for panel in panels if "org.kde.mac.tahoe.liquid.icontasks" in panel["widgets"]]
        if any(panel["hiding"] != "autohide" for panel in docks):
            raise RuntimeError("Dock is not using autohide")
    elif any("mac.tahoe" in widget or "mac-tahoe" in widget for widget in widgets):
        raise RuntimeError("Uninstall left themed widgets on the desktop")


def verify_last_run(state: dict, mode: str) -> None:
    expected = "uninstall" if mode == "uninstalled" else "install"
    if (state.get("status") != "completed" or state.get("exit_code") != 0
            or state.get("script") != expected):
        raise RuntimeError(f"Installer did not record successful {expected} completion")


def probe(expected_distro: str, mode: str) -> dict:
    require_guest()
    import distro
    from utils import qdbus_cmd, restore_desktop_session_env

    restore_desktop_session_env()
    actual = distro.current_distro()
    wanted = {"opensuse": "opensuse-tumbleweed", "kubuntu": "ubuntu"}.get(expected_distro, expected_distro)
    if actual != wanted:
        raise RuntimeError(f"Expected {wanted}, guest reports {actual}")
    qdbus = qdbus_cmd()
    if not qdbus:
        raise RuntimeError("No Qt 6 D-Bus client")
    # Exiting shells can coexist briefly after installation; track the process
    # serving the desktop instead of every process with the same executable.
    shell_pid = run(qdbus, "org.freedesktop.DBus", "/org/freedesktop/DBus",
                    "org.freedesktop.DBus.GetConnectionUnixProcessID", "org.kde.plasmashell")
    compositor = run(qdbus, "org.freedesktop.DBus", "/org/freedesktop/DBus",
                     "org.freedesktop.DBus.GetConnectionUnixProcessID", "org.kde.KWin")
    script = '''print(JSON.stringify(panels().map(function(p) {
        return {id:p.id, location:p.location, hiding:p.hiding,
            widgets:p.widgets().map(function(w) { return w.type; })};
    })))'''
    panels = json.loads(run(qdbus, "org.kde.plasmashell", "/PlasmaShell",
                            "org.kde.PlasmaShell.evaluateScript", script))
    effects = run(qdbus, "org.kde.KWin", "/Effects",
                  "org.kde.kwin.Effects.loadedEffects").splitlines()
    report = {
        "distro": actual,
        "os_release": Path("/etc/os-release").read_text(),
        "kernel": run("uname", "-r"),
        "plasma": run("plasmashell", "--version"),
        "qt": run("qmake6", "-query", "QT_VERSION"),
        "init_system": distro.init_system(),
        "shell_pid": shell_pid,
        "compositor_pid": compositor,
        "panels": panels,
        "loaded_effects": effects,
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "original_gtk_profile_saved": (Path.home() / "vm-original-gtk-4.0").is_dir(),
    }
    if mode in ("light", "dark"):
        from screenshot_checks import check_session
        from steps.acrylic_glass import _running_build_matches

        report["appearance"] = check_session(mode)
        verify_panels(panels, installed=True)
        if "liquidglass" not in effects:
            raise RuntimeError("Acrylic Glass is not loaded in the live compositor")
        report["glass_build_matches"] = _running_build_matches()
        if report["glass_build_matches"] is not True:
            raise RuntimeError("Running Acrylic Glass build identity is unconfirmed")
    elif mode == "uninstalled":
        verify_panels(panels, installed=False)
        if "liquidglass" in effects:
            raise RuntimeError("Uninstall left Acrylic Glass loaded")
    if mode != "baseline":
        state = Path.home() / ".local/state/mac-tahoe-liquid-kde/last-run.json"
        report["last_run"] = json.loads(state.read_text())
        verify_last_run(report["last_run"], mode)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--distro", required=True)
    parser.add_argument("--mode", choices=("baseline", "light", "dark", "uninstalled"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {"mode": args.mode, "expected_distro": args.distro,
              "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        report.update(probe(args.distro, args.mode))
        report["status"] = "pass"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        report.update(status="fail", error=str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
