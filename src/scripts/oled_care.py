#!/usr/bin/env python3
"""OLED care pixel-shift: `mac-tahoe-oled-care {shift|restore|status}`.
Fill-length panels cycle height (Plasma clamps their offset); others
cycle offset. When a panel's geometry != base + last delta the user
moved it — re-capture the base, never fight a deliberate change."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


# Offsets walk a triangle wave around the base; heights use the |offset|
# wave so a panel only grows — it never renders thinner than its base.
DEFAULT_MAX_SHIFT_PX = 8
MAX_SHIFT_CEILING_PX = 16
SHIFT_STEP_PX = 2

_QDBUS_TIMEOUT_SECONDS = 15


def clamp_max_px(value: object) -> int:
    try:
        px = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_MAX_SHIFT_PX
    return max(1, min(MAX_SHIFT_CEILING_PX, px))


def build_patterns(max_px: int) -> tuple[list[int], list[int]]:
    """Triangle wave 0→M→0→-M→0 in SHIFT_STEP_PX steps plus its
    absolute-value twin for the height knob. One index drives both."""
    max_px = clamp_max_px(max_px)
    s = SHIFT_STEP_PX
    offsets = (list(range(0, max_px, s)) + list(range(max_px, 0, -s)) +
               list(range(0, -max_px, -s)) + list(range(-max_px, 0, s)))
    return offsets, [abs(d) for d in offsets]


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _state_file() -> Path:
    state_home = Path(os.environ.get("XDG_STATE_HOME") or
                      str(Path.home() / ".local/state"))
    return state_home / "mac-tahoe-liquid-kde" / "oled-care.json"


_SESSION_ENV_KEYS = frozenset({
    "DBUS_SESSION_BUS_ADDRESS",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "XAUTHORITY",
    "XDG_RUNTIME_DIR",
})
_PROC_ROOT = Path("/proc")


def _sync_session_env_runtime_dir() -> None:
    """Reconstruct the session env from ``/run/user/$UID``.

    XDG_RUNTIME_DIR is provided by the session runtime (systemd-logind or
    elogind); its well-known Wayland and DBus sockets work without knowing
    which init launched the scheduled command.
    """
    xrd = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    if not Path(xrd).is_dir():
        return
    os.environ.setdefault("XDG_RUNTIME_DIR", xrd)

    if "WAYLAND_DISPLAY" not in os.environ:
        # Sockets are named wayland-0, wayland-1, …; pick the lowest that
        # exists. Store the bare name — Qt resolves it against XDG_RUNTIME_DIR.
        for sock in sorted(Path(xrd).glob("wayland-*")):
            if sock.is_socket() and not sock.name.endswith(".lock"):
                os.environ["WAYLAND_DISPLAY"] = sock.name
                break

    if "DBUS_SESSION_BUS_ADDRESS" not in os.environ:
        bus = Path(xrd) / "bus"
        if bus.is_socket():
            os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus}"


def _sync_session_env_from_plasmashell() -> None:
    """Recover X11 and any missing values from a same-user Plasma shell."""
    try:
        uid = int(os.environ.get("SUDO_UID") or os.getuid())
    except ValueError:
        uid = os.getuid()
    try:
        processes = list(_PROC_ROOT.iterdir())
    except OSError:
        return
    for process in processes:
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != uid:
                continue
            if (process / "comm").read_text().strip() != "plasmashell":
                continue
            raw = (process / "environ").read_bytes()
        except OSError:
            continue
        for entry in raw.split(b"\0"):
            key_raw, sep, value_raw = entry.partition(b"=")
            key = key_raw.decode(errors="ignore")
            if not sep or key not in _SESSION_ENV_KEYS or key in os.environ:
                continue
            value = value_raw.decode(errors="ignore")
            if value:
                os.environ[key] = value
        break


def _sync_session_env() -> None:
    """Best-effort recovery of the desktop session env for scheduled
    fires. Runtime sockets cover Wayland/DBus, while a same-user plasmashell
    supplies X11/Xauthority. Neither path depends on the host init system."""
    _sync_session_env_runtime_dir()
    _sync_session_env_from_plasmashell()


def _evaluate_script(script: str) -> str | None:
    """Run a Plasma scripting snippet via qdbus; returns its print()
    output, or None when plasmashell is unreachable (normal early in boot)."""
    _sync_session_env()
    for q in ("qdbus6", "qdbus-qt6", "qdbus"):
        if not _have(q):
            continue
        try:
            res = subprocess.run(
                [q, "org.kde.plasmashell", "/PlasmaShell",
                 "org.kde.PlasmaShell.evaluateScript", script],
                check=False, capture_output=True, text=True,
                timeout=_QDBUS_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return res.stdout if res.returncode == 0 else None
    return None


_EMPTY_STATE = {"index": 0, "last_off": 0, "last_h": 0, "panels": {}}


def load_state() -> dict:
    """Applied deltas are stored, not recomputed — restore stays correct
    even when --oled-max-shift changed since the last shift."""
    try:
        data = json.loads(_state_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(_EMPTY_STATE)
    if not isinstance(data, dict):
        return dict(_EMPTY_STATE)

    def _delta(key: str) -> int:
        v = data.get(key)
        if not isinstance(v, int):
            return 0
        return max(-MAX_SHIFT_CEILING_PX, min(MAX_SHIFT_CEILING_PX, v))

    index = data.get("index")
    panels = data.get("panels")
    return {
        "index": index if isinstance(index, int) and index >= 0 else 0,
        "last_off": _delta("last_off"),
        "last_h": _delta("last_h"),
        "panels": panels if isinstance(panels, dict) else {},
    }


def save_state(state: dict) -> None:
    path = _state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state) + "\n", encoding="utf-8")


def build_shift_script(panels: dict, last_off: int, last_h: int,
                       next_off: int, next_h: int) -> str:
    """One atomic read-rebase-apply pass inside plasmashell; prints the
    rebased base map as JSON so Python persists it in one round-trip."""
    return f"""
var bases = {json.dumps(panels)};
var lastOff = {last_off}, nextOff = {next_off};
var lastH = {last_h}, nextH = {next_h};
var out = {{}};
var all = panels();
for (var i = 0; i < all.length; i++) {{
    var p = all[i];
    var key = String(p.id);
    var fill = false;
    try {{ fill = (p.lengthMode == "fill"); }} catch (e) {{}}
    var base = bases[key];
    if (!base) base = {{offset: p.offset, height: p.height}};
    if (fill) {{
        if (p.height != base.height + lastH) base.height = p.height;
        base.offset = p.offset;
        p.height = base.height + nextH;
    }} else {{
        if (p.offset != base.offset + lastOff) base.offset = p.offset;
        base.height = p.height;
        p.offset = base.offset + nextOff;
    }}
    out[key] = {{offset: base.offset, height: base.height}};
}}
print(JSON.stringify(out));
"""


def build_restore_script(panels: dict, last_off: int, last_h: int) -> str:
    """Undo exactly the delta we applied. A panel whose geometry no
    longer matches base + delta was changed by the user — leave it."""
    return f"""
var bases = {json.dumps(panels)};
var lastOff = {last_off};
var lastH = {last_h};
var all = panels();
for (var i = 0; i < all.length; i++) {{
    var p = all[i];
    var base = bases[String(p.id)];
    if (!base) continue;
    var fill = false;
    try {{ fill = (p.lengthMode == "fill"); }} catch (e) {{}}
    if (fill) {{
        if (p.height == base.height + lastH) p.height = base.height;
    }} else {{
        if (p.offset == base.offset + lastOff) p.offset = base.offset;
    }}
}}
print("restored");
"""


def _parse_panel_map(output: str) -> dict | None:
    for line in reversed((output or "").strip().splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def shift(max_px: int = DEFAULT_MAX_SHIFT_PX) -> int:
    offsets, heights = build_patterns(max_px)
    state = load_state()
    next_index = (state["index"] + 1) % len(offsets)
    next_off, next_h = offsets[next_index], heights[next_index]
    output = _evaluate_script(
        build_shift_script(state["panels"], state["last_off"],
                           state["last_h"], next_off, next_h))
    if output is None:
        # Nothing shifted — keep state so the next fire resumes here.
        return 0
    panels = _parse_panel_map(output)
    if panels is None:
        print("oled care: could not parse panel state from plasmashell",
              file=sys.stderr)
        return 1
    save_state({"index": next_index, "last_off": next_off,
                "last_h": next_h, "panels": panels})
    return 0


def restore() -> int:
    state = load_state()
    if not state["panels"]:
        return 0
    output = _evaluate_script(
        build_restore_script(state["panels"], state["last_off"],
                             state["last_h"]))
    if output is None:
        # Keep state so the next shift/restore corrects the ≤2 px residue.
        print("oled care: plasmashell unreachable — geometry not restored",
              file=sys.stderr)
        return 0
    try:
        _state_file().unlink()
    except OSError:
        pass
    return 0


def status() -> int:
    state = load_state()
    if not state["panels"]:
        print("inactive (no panel state)")
        return 0
    print(json.dumps(state, indent=2))
    return 0


USAGE = "Usage: mac-tahoe-oled-care {shift [--max-px N]|restore|status}"


def _parse_max_px(args: list[str]) -> int:
    max_px = DEFAULT_MAX_SHIFT_PX
    i = 0
    while i < len(args):
        if args[i] == "--max-px" and i + 1 < len(args):
            max_px = args[i + 1]
            i += 2
            continue
        if args[i].startswith("--max-px="):
            max_px = args[i].split("=", 1)[1]
        i += 1
    return clamp_max_px(max_px)


def main(argv: list[str]) -> int:
    if not argv:
        print(USAGE, file=sys.stderr)
        return 1
    cmd = argv[0]
    if cmd == "shift":
        return shift(_parse_max_px(argv[1:]))
    if cmd == "restore":
        return restore()
    if cmd == "status":
        return status()
    print(USAGE, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
