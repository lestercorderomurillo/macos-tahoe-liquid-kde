#!/usr/bin/env python3
"""Thin QML wrapper for the existing install / uninstall commands.

This does not replace the Python installer backend. It either:

1. loads ``preview_installer.qml`` via PyQt6 (preferred) so we can
   attach KWin's blur-behind effect to the window the same way the
   AboutWindow gets it inside plasmashell — falling back to ``qml6``
   as a subprocess if PyQt6 is not installed, or
2. opens ``sudo ./install`` / ``sudo ./uninstall`` in a terminal.

Keeping the real work in the existing CLI preserves the current sudo
flow, including the ``SUDO_USER`` / ``SUDO_UID`` handoff that the
installer relies on after privilege drop.
"""

from __future__ import annotations

import argparse
import json
import os
import pwd
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from paths import CONFIG_FILE, REPO_ROOT
from cli import ALL_FEATURES, DEFAULT_FEATURES, FEATURE_DESC
from log import DONE_MARKER, PROGRESS_FILE


PREVIEW_QML = REPO_ROOT / "src/scripts/preview_installer.qml"
_QML_RUNNERS = ("qmlscene6", "qmlscene", "qml6")

_ACTION_COMMANDS = {
    "install": "sudo ./install",
    "uninstall": "sudo ./uninstall",
    "preflight": "sudo ./install --preflight",
}


def command_for_action(action: str) -> str:
    """Display-friendly form, also what tests assert. Real launch uses
    :func:`escalated_command_for_action` which picks pkexec when sudo
    is unavailable so users who aren't in sudoers can still install."""
    return _ACTION_COMMANDS[action]


def escalated_command_for_action(action: str, headless: bool = False) -> str:
    """Shell command to run an action as root — prefers pkexec over sudo.

    ``pkexec`` (polkit) pops a graphical password prompt and works on
    any host with a polkit agent, including users not in the sudoers
    file. ``sudo`` is the fallback. The ``SUDO_USER=… SUDO_UID=…`` shim
    bridges the escalator's wiped environment back to the variables the
    install scripts rely on to drop privileges mid-install.

    For pkexec we expand ``./install`` to its absolute path because
    pkexec ignores the calling shell's cwd, so a bare ``./install``
    would fail with ``No such file or directory``.

    ``headless=True`` is the in-UI path (the install runs in the
    background and the UI watches the progress file): it adds
    ``MTTKDE_NO_CONFIRM=1`` so the install's interactive confirm prompt
    is skipped — there's no tty, and the UI shows its own warning — and
    pins ``MTTKDE_PROGRESS_FILE`` so the root-side install writes the
    very file this process watches. Without ``MTTKDE_NO_CONFIRM`` the
    background install blocks forever on ``input()`` and the bar never
    moves. The default (``headless=False``) is the terminal path, where
    the confirm prompt is shown interactively.
    """
    base = _ACTION_COMMANDS[action]
    target = base[len("sudo "):] if base.startswith("sudo ") else base

    # Headless vars apply to BOTH escalators: the background install must
    # skip its tty confirm prompt and write the progress file we watch.
    headless_pairs = []
    if headless:
        headless_pairs = [
            "MTTKDE_NO_CONFIRM=1",
            f"MTTKDE_PROGRESS_FILE={shlex.quote(PROGRESS_FILE)}",
        ]

    if shutil.which("pkexec"):
        # pkexec wipes the environment, so it also needs the SUDO_* shim
        # the install relies on to drop privileges mid-run.
        uid = os.getuid()
        try:
            pw = pwd.getpwuid(uid)
            user, gid = pw.pw_name, pw.pw_gid
        except KeyError:
            user, gid = os.environ.get("USER", "user"), os.getgid()
        env_str = " ".join([
            f"SUDO_USER={shlex.quote(user)}",
            f"SUDO_UID={uid}",
            f"SUDO_GID={gid}",
            f"HOME={shlex.quote(os.path.expanduser('~'))}",
            "PYTHONUNBUFFERED=1",
            *headless_pairs,
        ])
        # Replace the relative ``./install`` / ``./uninstall`` with the
        # absolute path; everything after the binary stays as-is (e.g.
        # ``--preflight``). pkexec ignores the caller's cwd.
        parts = target.split(" ", 1)
        if parts[0].startswith("./"):
            parts[0] = shlex.quote(str(REPO_ROOT / parts[0][2:]))
        absolute_target = " ".join(parts)
        return f"pkexec env {env_str} {absolute_target}"

    # sudo fallback: sudo already exports SUDO_USER / SUDO_UID itself, so
    # only the headless vars need forcing (as leading NAME=value args,
    # which sudo permits for non-protected vars).
    prefix = (" ".join(headless_pairs) + " ") if headless_pairs else ""
    return f"sudo {prefix}{target}"

_TERMINAL_BUILDERS = (
    ("konsole", lambda shell_cmd: ["konsole", "--noclose", "-e",
                                   "bash", "-lc", shell_cmd]),
    ("kgx", lambda shell_cmd: ["kgx", "--", "bash", "-lc", shell_cmd]),
    ("gnome-terminal", lambda shell_cmd: ["gnome-terminal", "--",
                                          "bash", "-lc", shell_cmd]),
    ("ptyxis", lambda shell_cmd: ["ptyxis", "--", "bash", "-lc", shell_cmd]),
    ("xterm", lambda shell_cmd: ["xterm", "-hold", "-e",
                                 "bash", "-lc", shell_cmd]),
    ("kitty", lambda shell_cmd: ["kitty", "bash", "-lc", shell_cmd]),
    ("alacritty", lambda shell_cmd: ["alacritty", "-e",
                                     "bash", "-lc", shell_cmd]),
    ("wezterm", lambda shell_cmd: ["wezterm", "start",
                                   "--always-new-process", "--",
                                   "bash", "-lc", shell_cmd]),
)


def _restore_user_session_env(uid: int) -> None:
    runtime_dir = Path(f"/run/user/{uid}")
    bus = runtime_dir / "bus"
    if runtime_dir.is_dir():
        os.environ.setdefault("XDG_RUNTIME_DIR", str(runtime_dir))
    if bus.exists():
        os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={bus}")


def drop_root_to_invoking_user() -> int:
    if os.geteuid() != 0:
        return 0

    sudo_user = os.environ.get("SUDO_USER")
    sudo_uid_str = os.environ.get("SUDO_UID")
    sudo_gid_str = os.environ.get("SUDO_GID")
    if not sudo_user or not sudo_uid_str or not sudo_gid_str:
        print(
            "installer UI must be launched from a regular desktop user "
            "(or via sudo from that user session).",
            file=sys.stderr,
        )
        return 1

    sudo_uid = int(sudo_uid_str)
    sudo_gid = int(sudo_gid_str)
    try:
        user_home = pwd.getpwuid(sudo_uid).pw_dir
    except KeyError:
        user_home = f"/home/{sudo_user}"

    os.environ["HOME"] = user_home
    os.environ["USER"] = sudo_user
    os.environ["LOGNAME"] = sudo_user
    _restore_user_session_env(sudo_uid)

    # Drop real/effective/saved IDs permanently so Qt does not see a
    # setuid-style mismatch when the preview window starts.
    os.setresgid(sudo_gid, sudo_gid, sudo_gid)
    os.setresuid(sudo_uid, sudo_uid, sudo_uid)
    return 0


def _shell_command(action: str) -> str:
    repo = shlex.quote(str(REPO_ROOT))
    return f"cd {repo} && {escalated_command_for_action(action)}"


def _terminal_specs(shell_cmd: str) -> list[tuple[str, list[str]]]:
    return [(name, build(shell_cmd)) for name, build in _TERMINAL_BUILDERS]


def launch_action(action: str) -> dict[str, object]:
    display_cmd = command_for_action(action)
    shell_cmd = _shell_command(action)
    last_error = ""
    saw_terminal = False

    for terminal, argv in _terminal_specs(shell_cmd):
        if not shutil.which(terminal):
            continue
        saw_terminal = True
        try:
            subprocess.Popen(
                argv,
                cwd=str(REPO_ROOT),
                start_new_session=True,
            )
        except OSError as exc:
            last_error = f"{terminal}: {exc}"
            continue
        return {
            "ok": True,
            "action": action,
            "terminal": terminal,
            "command": display_cmd,
            "message": f"Launching {display_cmd} in {terminal}.",
        }

    if saw_terminal and last_error:
        message = f"Could not open a terminal window ({last_error})."
    else:
        message = (
            "No supported terminal emulator was found. "
            "Install Konsole or run the command manually from the repo root."
        )
    return {
        "ok": False,
        "action": action,
        "terminal": "",
        "command": display_cmd,
        "message": message,
    }


def _enable_kwin_blur(window) -> None:
    """Ask KWin to blur whatever sits behind ``window``.

    The AboutWindow gets this for free because plasmashell loads it
    inside Plasma's QML context, where KWin applies surface effects to
    everything plasmashell owns. A standalone ``qml6`` window does not
    — KWin treats it like any other unprivileged toplevel and skips
    blur, which is why the installer otherwise renders opaque.

    KWindowEffects::enableBlurBehind speaks the right protocol on both
    X11 (sets ``_KDE_NET_WM_BLUR_BEHIND_REGION``) and Wayland (uses the
    kde-wayland-blur protocol via the KDE Qt platform plugin). There
    are no Python bindings for KF6 on Arch / CachyOS, so we call the
    C++ symbol directly via ctypes. A failure here is non-fatal — the
    window still works, it just renders without blur.
    """
    import ctypes
    try:
        import sip  # PyQt6's sip is exposed as a sibling module
    except ImportError:
        from PyQt6 import sip  # type: ignore

    from PyQt6.QtGui import QRegion

    try:
        lib = ctypes.CDLL("libKF6WindowSystem.so.6")
    except OSError:
        return

    # KWindowEffects::enableBlurBehind(QWindow*, bool, QRegion const&)
    fn = getattr(
        lib,
        "_ZN14KWindowEffects16enableBlurBehindEP7QWindowbRK7QRegion",
        None,
    )
    if fn is None:
        return

    empty_region = QRegion()
    window_ptr = sip.unwrapinstance(window)
    region_ptr = sip.unwrapinstance(empty_region)

    fn.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_void_p]
    fn.restype = None
    fn(ctypes.c_void_p(window_ptr), True, ctypes.c_void_p(region_ptr))


def _make_installer_bridge():
    """Build the QObject that the QML side drives the install through.

    The QML calls ``installer.start("install" | "uninstall")``. The
    bridge launches the existing CLI in the BACKGROUND (via pkexec/sudo,
    no terminal) and does NOT parse its stdout — that path deadlocks the
    moment the install hits its ``confirm()`` prompt with no controlling
    tty, which is exactly why the bar used to freeze after the password
    dialog.

    Instead the install mirrors each step title into a fixed progress
    file (see ``log.PROGRESS_FILE``); the bridge watches that file and
    reads the step titles as they appear. The install is launched with
    ``MTTKDE_NO_CONFIRM=1`` so the in-terminal warning is skipped — the
    UI shows its own confirmation up front.

    Signals:
        currentStepChanged()   — most recent step title (a property read)
        progressChanged()      — 0.0-1.0 fraction
        runningChanged()       — flips false when the run finishes
        finished(int exitCode) — exit code from the ``__DONE__`` marker
                                 (or the process, as a backstop); QML
                                 opens the error window when non-zero
        logAppended(str)       — step titles, for the error window's tail
    """
    from PyQt6.QtCore import (
        QFileSystemWatcher, QObject, QProcess, QTimer,
        pyqtProperty, pyqtSignal, pyqtSlot,
    )

    # Rough upper bound on the number of steps a full install emits —
    # used to project a 0.0-1.0 fraction. The bar snaps to 1.0 on the
    # ``__DONE__`` marker, so a low estimate only means it moves faster,
    # never that it overshoots: ``min(step / total, 0.95)`` keeps a
    # little headroom so the bar always has somewhere to grow.
    _ESTIMATED_TOTAL_STEPS = 25

    class InstallerBridge(QObject):
        currentStepChanged = pyqtSignal()
        progressChanged = pyqtSignal()
        runningChanged = pyqtSignal()
        finished = pyqtSignal(int)
        logAppended = pyqtSignal(str)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._proc: QProcess | None = None
            self._current_step = ""
            self._step_index = 0
            self._progress = 0.0
            self._running = False
            self._log_lines: list[str] = []
            self._read_offset = 0
            self._line_buf = ""
            self._exit_code: int | None = None

            # QFileSystemWatcher catches most writes, but it can coalesce
            # rapid appends and drops the path when the file is truncated
            # / recreated at run start. A short poll timer backs it up so
            # no step title is ever missed.
            self._watcher = QFileSystemWatcher(self)
            self._watcher.fileChanged.connect(self._read_progress)
            self._poll = QTimer(self)
            self._poll.setInterval(250)
            self._poll.timeout.connect(self._read_progress)

        @pyqtProperty(str, notify=currentStepChanged)
        def currentStep(self) -> str:
            return self._current_step

        @pyqtProperty(float, notify=progressChanged)
        def progress(self) -> float:
            return self._progress

        @pyqtProperty(bool, notify=runningChanged)
        def running(self) -> bool:
            return self._running

        @pyqtSlot(result=str)
        def logTail(self) -> str:
            return "\n".join(self._log_lines[-200:])

        @pyqtSlot(str)
        def start(self, action: str) -> None:
            if self._running or action not in _ACTION_COMMANDS:
                return
            self._log_lines.clear()
            self._current_step = "Starting…"
            self._step_index = 0
            self._progress = 0.0
            self._read_offset = 0
            self._line_buf = ""
            self._exit_code = None
            self.currentStepChanged.emit()
            self.progressChanged.emit()

            # Truncate the progress file ourselves before launch so we
            # never read a stale run's titles in the window before the
            # root-side install calls progress_reset(). Best-effort.
            try:
                with open(PROGRESS_FILE, "w", encoding="utf-8"):
                    pass
            except OSError:
                pass

            # Watch the file (re-add each run — truncation can drop it).
            if PROGRESS_FILE not in self._watcher.files():
                self._watcher.addPath(PROGRESS_FILE)
            self._poll.start()

            shell_cmd = escalated_command_for_action(action, headless=True)
            self._proc = QProcess(self)
            self._proc.setProcessChannelMode(
                QProcess.ProcessChannelMode.MergedChannels)
            self._proc.setWorkingDirectory(str(REPO_ROOT))
            self._proc.finished.connect(self._on_proc_finished)
            # bash -lc so the shell composes "env KEY=val pkexec ..."
            # uniformly; -l loads the profile so ~/.local/bin is on PATH.
            self._proc.start("bash", ["-lc", shell_cmd])
            self._running = True
            self.runningChanged.emit()

        @pyqtSlot()
        def cancel(self) -> None:
            if self._proc and self._proc.state() != QProcess.ProcessState.NotRunning:
                self._proc.kill()

        def _read_progress(self) -> None:
            """Read whatever new lines have been appended to the progress
            file since last time and update step / progress / done."""
            try:
                with open(PROGRESS_FILE, "r", encoding="utf-8") as fh:
                    fh.seek(self._read_offset)
                    chunk = fh.read()
                    self._read_offset = fh.tell()
            except OSError:
                return

            if not chunk:
                return
            self._line_buf += chunk
            while "\n" in self._line_buf:
                line, self._line_buf = self._line_buf.split("\n", 1)
                self._handle_record(line.rstrip("\r"))

        def _handle_record(self, record: str) -> None:
            if not record:
                return
            parts = record.split("\t", 1)
            head = parts[0]
            if head == DONE_MARKER:
                code = 0
                if len(parts) > 1:
                    try:
                        code = int(parts[1])
                    except ValueError:
                        code = 0
                self._finish(code)
                return
            # A step record: "<n>\t<title>".
            title = parts[1] if len(parts) > 1 else head
            self._log_lines.append(title)
            if len(self._log_lines) > 2000:
                del self._log_lines[:1000]
            self.logAppended.emit(title)
            self._current_step = title
            self._step_index += 1
            self._progress = min(
                self._step_index / _ESTIMATED_TOTAL_STEPS, 0.95)
            self.currentStepChanged.emit()
            self.progressChanged.emit()

        def _on_proc_finished(self, code: int, _status) -> None:
            # Drain any final records the file write beat us to, then fall
            # back to the process exit code if the install died before
            # writing __DONE__ (crash / killed / pkexec auth declined).
            self._read_progress()
            if self._exit_code is None:
                self._finish(code)

        def _finish(self, code: int) -> None:
            if self._exit_code is not None:
                return
            self._exit_code = code
            self._poll.stop()
            if PROGRESS_FILE in self._watcher.files():
                self._watcher.removePath(PROGRESS_FILE)
            # Snap to a full bar for the brief success-view moment.
            self._progress = 1.0
            self.progressChanged.emit()
            self._running = False
            self.runningChanged.emit()
            self.finished.emit(code)

    return InstallerBridge()


def _launch_preview_pyqt() -> int:
    """Load InstallerWindow via PyQt6 so we can attach a KWin blur."""
    # Force the Plasma desktop style so the installer's QQC2 buttons,
    # switches, and scroll bars look exactly like the AboutWindow does
    # inside plasmashell — same padding, corner radius, hover, accent
    # color. Without this, standalone Qt apps default to the Fusion
    # style and the installer reads as a foreign Qt window on KDE.
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")

    try:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QGuiApplication
        from PyQt6.QtQml import QQmlApplicationEngine
    except ImportError:
        return -1  # signal "PyQt6 unavailable" to the caller

    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    engine = QQmlApplicationEngine()
    bridge = _make_installer_bridge()
    engine.rootContext().setContextProperty("installer", bridge)
    engine.load(QUrl.fromLocalFile(str(PREVIEW_QML)))
    roots = engine.rootObjects()
    if not roots:
        return 1
    window = roots[0]
    _enable_kwin_blur(window)
    return app.exec()


def launch_preview() -> int:
    rc = _launch_preview_pyqt()
    if rc >= 0:
        return rc

    runner = next((name for name in _QML_RUNNERS if shutil.which(name)), "")
    if not runner:
        print("qmlscene6/qmlscene/qml6 not found — install qt6-declarative", file=sys.stderr)
        return 1
    if not PREVIEW_QML.is_file():
        print(f"preview QML missing: {PREVIEW_QML}", file=sys.stderr)
        return 1
    return subprocess.run(
        [runner, str(PREVIEW_QML)],
        check=False,
        cwd=str(REPO_ROOT),
    ).returncode


def dump_features() -> dict[str, object]:
    """Return current feature state for the Features window.

    Reads ``features.json`` if it exists; otherwise returns
    DEFAULT_FEATURES. The QML side renders a toggle per entry in
    ``items`` (order preserved) with the description below the label.
    """
    state: dict[str, object] = dict(DEFAULT_FEATURES)
    if CONFIG_FILE.is_file():
        try:
            saved = json.loads(CONFIG_FILE.read_text())
            if isinstance(saved, dict):
                for key, value in saved.items():
                    if key in state:
                        state[key] = value
        except (OSError, ValueError):
            pass

    items = [
        {
            "key": key,
            "label": key.replace("_", " ").title(),
            "description": FEATURE_DESC.get(key, ""),
            "enabled": bool(state.get(key, True)),
        }
        for key in ALL_FEATURES
        if key != "no_download"  # internal flag, not a user-facing feature
    ]
    return {"items": items, "config_path": str(CONFIG_FILE)}


def save_features(payload: dict[str, object]) -> dict[str, object]:
    """Persist toggles received from the QML side into ``features.json``."""
    state: dict[str, object] = dict(DEFAULT_FEATURES)
    if CONFIG_FILE.is_file():
        try:
            saved = json.loads(CONFIG_FILE.read_text())
            if isinstance(saved, dict):
                state.update({k: v for k, v in saved.items() if k in state})
        except (OSError, ValueError):
            pass

    for key, value in payload.items():
        if key in state and isinstance(value, bool):
            state[key] = value

    try:
        CONFIG_FILE.write_text(json.dumps(state, indent=2) + "\n")
    except OSError as exc:
        return {"ok": False, "message": str(exc)}
    return {"ok": True, "message": f"Saved to {CONFIG_FILE.name}"}


def main(argv: list[str]) -> int:
    rc = drop_root_to_invoking_user()
    if rc != 0:
        return rc

    parser = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name or "installer",
        description=__doc__,
    )
    parser.add_argument(
        "--launch",
        choices=sorted(_ACTION_COMMANDS),
        help="Open the existing CLI command for the chosen action in a terminal.",
    )
    parser.add_argument(
        "--dump-features",
        action="store_true",
        help="Print current feature state as JSON (for the Features window).",
    )
    parser.add_argument(
        "--save-features",
        metavar="JSON",
        help="Persist a JSON object of {feature: bool} into features.json.",
    )
    args = parser.parse_args(argv)

    if args.launch:
        payload = launch_action(args.launch)
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if payload["ok"] else 1

    if args.dump_features:
        print(json.dumps(dump_features(), ensure_ascii=False))
        return 0

    if args.save_features is not None:
        try:
            data = json.loads(args.save_features)
        except ValueError as exc:
            print(json.dumps({"ok": False, "message": f"bad JSON: {exc}"}))
            return 1
        result = save_features(data if isinstance(data, dict) else {})
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["ok"] else 1

    return launch_preview()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
