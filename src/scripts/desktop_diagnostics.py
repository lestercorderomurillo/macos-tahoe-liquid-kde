"""Print a read-only Plasma failure report from the affected user's desktop session."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess


def probe(command, runner=subprocess.run):
    try:
        result = runner(command, capture_output=True, text=True, errors="replace", timeout=6)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": type(exc).__name__}
    return {"exit": result.returncode, "output": (result.stdout or result.stderr).strip()[:24000]}


def panel_inventory(qdbus, runner=subprocess.run):
    if not qdbus:
        return {"error": "qdbus unavailable"}
    script = """print(JSON.stringify(panels().map(p => ({id:p.id,screen:p.screen,
      edge:p.location,hiding:p.hiding,widgets:p.widgets().map(w => ({
      type:w.type,registered:knownWidgetTypes.includes(w.type)}))}))))"""
    reply = probe([qdbus, "org.kde.plasmashell", "/PlasmaShell",
                   "org.kde.PlasmaShell.evaluateScript", script], runner)
    if reply.get("exit") != 0:
        return reply
    try:
        panels = json.loads(reply["output"])
    except ValueError:
        return {"error": "Incomplete Plasma panel inventory"}
    return {"panels": panels} if isinstance(panels, list) else {"error": "Unexpected Plasma reply"}


def report(minutes):
    result = {"session": os.getenv("XDG_SESSION_TYPE"), "virtualization": probe(["systemd-detect-virt"])}
    qdbus = next((name for name in ("qdbus6", "qdbus-qt6", "qdbus") if shutil.which(name)), None)
    if qdbus:
        result["panels"] = panel_inventory(qdbus)
        kwin = probe([qdbus, "org.kde.KWin", "/KWin", "org.kde.KWin.supportInformation"])
        result["graphics"] = {**kwin, "output": "\n".join(
            line for line in kwin.get("output", "").splitlines() if line.startswith(
                ("KWin version:", "Qt Version:", "Compositing Type:", "OpenGL vendor string:",
                 "OpenGL renderer string:", "OpenGL version string:", "Driver:")))}
    command = None
    if Path(__file__).with_name("distro.py").is_file():
        from distro import user_service_manager_command
        command = user_service_manager_command(
            "show", "plasma-plasmashell.service", "plasma-kwin_wayland.service",
            "plasma-kwin_x11.service", "-p", "Id,LoadState,ActiveState,Result,NRestarts,MainPID")
    if command:
        result["services"] = probe(command)
    else:
        result["desktop_processes"] = probe(["pgrep", "-l", "-u", str(os.getuid()),
                                             "-x", "plasmashell|kwin_wayland|kwin_x11"])
    result["journal"] = probe(["journalctl", "--user", "-b", "--since", f"{minutes} minutes ago",
                               "--no-pager", "-o", "short-iso", "-n", "80", "--case-sensitive=no",
                               "--grep", "error|failed|crash|segfault|restart|unavailable|not installed|"
                               "could not|cannot load|undefined symbol", "_COMM=plasmashell",
                               "_COMM=kwin_wayland", "_COMM=kwin_x11", "_COMM=systemd"])
    state = Path(os.environ.get("XDG_STATE_HOME") or Path.home()/".local/state")
    try:
        previous = json.loads((state/"mac-tahoe-liquid-kde/last-run.json").read_text())
        result["last_install_operation"] = {key: previous.get(key) for key in
                                            ("script", "install", "status", "started_at", "finished_at", "steps")}
    except (OSError, ValueError, AttributeError) as exc:
        result["last_install_operation"] = {"error": type(exc).__name__}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", default=5, type=int)
    args = parser.parse_args()
    if not 1 <= args.minutes <= 60:
        parser.error("--minutes must be between 1 and 60")
    print(json.dumps(report(args.minutes), indent=2))
