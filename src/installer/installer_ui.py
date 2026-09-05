#!/usr/bin/env python3
"""QML wrapper for the install / uninstall commands."""

from __future__ import annotations

import argparse
import errno
import json
import os
import pwd
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Make the CLI engine (src/scripts) importable whether launched via the
# root ./installer or imported directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from paths import CONFIG_FILE, REPO_ROOT, read_version
from cli import (
    ALL_FEATURES, DEFAULT_FEATURES, FEATURE_DESC,
    fetch_latest_release, parse_semver,
)
from log import DONE_MARKER


PREVIEW_QML = Path(__file__).resolve().parent / "preview_installer.qml"

_ACTION_COMMANDS = {
    "install": "sudo ./install",
    "uninstall": "sudo ./uninstall",
    "preflight": "sudo ./install --preflight",
}

_SUPERVISOR_POLL_SECONDS = 0.05


def _create_private_run_file(prefix: str) -> str:
    """Create one private control channel before privilege escalation."""
    fd, path = tempfile.mkstemp(prefix=prefix, dir="/tmp")
    try:
        os.fchmod(fd, 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise OSError(errno.EPERM, "secure run file is not regular")
        if info.st_uid != os.geteuid():
            raise OSError(errno.EPERM, "secure run file has the wrong owner")
        if info.st_nlink != 1:
            raise OSError(errno.EPERM, "secure run file has extra links")
    except BaseException:
        try:
            os.close(fd)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        raise
    try:
        os.close(fd)
    except OSError:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path


def _create_progress_file() -> str:
    return _create_private_run_file("mttkde-install-progress-")


def _create_cancel_file() -> str:
    return _create_private_run_file("mttkde-install-cancel-")


def _secure_run_file_fd(path: str, *, write: bool) -> int:
    flags = os.O_WRONLY if write else os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise OSError(errno.EPERM, "run file is not regular")
        if (info.st_uid != os.geteuid() or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o600):
            raise OSError(
                errno.EPERM, "run file owner, mode, or link count changed")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _mark_cancel_requested(path: str | None) -> bool:
    if path is None:
        return False
    fd: int | None = None
    try:
        fd = _secure_run_file_fd(path, write=True)
        os.ftruncate(fd, 0)
        payload = b"cancel\n"
        while payload:
            written = os.write(fd, payload)
            if written <= 0:
                raise OSError(errno.EIO, "short cancellation-token write")
            payload = payload[written:]
        return True
    except OSError:
        return False
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def _cancel_file_requested(path: str) -> bool:
    """Fail closed if the supervisor's exact control inode was replaced."""
    fd: int | None = None
    try:
        fd = _secure_run_file_fd(path, write=False)
        return bool(os.read(fd, 1))
    except OSError:
        return True
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def _isolate_supervisor_process_group() -> bool:
    """Detach the supervisor/escalator from the GUI's terminal group.

    Terminal Ctrl+C must reach the GUI, which records cancellation in the
    private token; it must not independently interrupt pkexec/sudo before the
    root CLI has armed its cooperative monitor. Only being the leader of a new
    session proves detachment from the GUI's controlling terminal.
    """
    try:
        os.setsid()
    except OSError:
        pass
    try:
        return os.getsid(0) == os.getpid()
    except OSError:
        return False


def _parse_done_record(record: str, *, terminated: bool = True) -> int | None:
    """Return a complete progress-protocol DONE record's exit code.

    A trailing buffer without a newline is not a complete protocol record:
    the writer may have been killed between writing the marker and its code.
    Likewise, a missing or malformed code must fall back to QProcess's real
    exit status rather than turning an interrupted install into GUI success.
    """
    if not terminated:
        return None
    head, separator, value = record.partition("\t")
    if head != DONE_MARKER or not separator:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _request_app_quit(app, bridge, shutdown: dict[str, bool]) -> None:
    """Keep Qt alive long enough for a cancelled install to be reaped."""
    if bridge.running:
        if not shutdown["requested"]:
            shutdown["requested"] = True
            bridge.cancel()
        return
    app.quit()


def command_for_action(action: str) -> str:
    return _ACTION_COMMANDS[action]


def escalated_command_for_action(
        action: str, headless: bool = False,
        progress_file: str | None = None,
        cancel_file: str | None = None) -> str:
    base = _ACTION_COMMANDS[action]
    target = base[len("sudo "):] if base.startswith("sudo ") else base

    headless_pairs = []
    if headless:
        if progress_file is None or cancel_file is None:
            raise ValueError(
                "headless installer launch requires progress and cancel files")
        headless_pairs = [
            "MTTKDE_NO_CONFIRM=1",
            f"MTTKDE_PROGRESS_FILE={shlex.quote(progress_file)}",
            f"MTTKDE_CANCEL_FILE={shlex.quote(cancel_file)}",
        ]

    if shutil.which("pkexec"):
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
        parts = target.split(" ", 1)
        if parts[0].startswith("./"):
            parts[0] = shlex.quote(str(REPO_ROOT / parts[0][2:]))
        absolute_target = " ".join(parts)
        return f"pkexec env {env_str} {absolute_target}"

    prefix = (" ".join(headless_pairs) + " ") if headless_pairs else ""
    return f"sudo {prefix}{target}"


def _supervise_action(action: str, progress_file: str,
                      cancel_file: str) -> int:
    """Run privilege escalation while remaining a signalable GUI child.

    pkexec replaces its caller with a real-root process, which a user-owned
    QProcess can no longer terminate.  This small same-user supervisor stays
    as QProcess's direct child.  The CLI's private token monitor owns actual
    cooperative cancellation, while the supervisor stays alive until the
    privileged child is reaped.  The GUI therefore never reports completion,
    removes the run's control files, or permits a second transaction while
    the first one can still change the system.
    """
    if action not in _ACTION_COMMANDS:
        return 2
    if not _isolate_supervisor_process_group():
        print("Could not isolate privileged installer supervisor",
              file=sys.stderr)
        return 1
    if _cancel_file_requested(cancel_file):
        return 130

    shell_cmd = escalated_command_for_action(
        action,
        headless=True,
        progress_file=progress_file,
        cancel_file=cancel_file,
    )
    try:
        child = subprocess.Popen(
            ["bash", "-lc", shell_cmd],
            cwd=str(REPO_ROOT),
        )
    except OSError as exc:
        print(f"Could not start privileged installer: {exc}", file=sys.stderr)
        return 1

    signal_cancelled = False

    def request_cancel(_signum, _frame) -> None:
        nonlocal signal_cancelled
        signal_cancelled = True

    previous_int = signal.signal(signal.SIGINT, request_cancel)
    previous_term = signal.signal(signal.SIGTERM, request_cancel)
    cancellation_seen = False
    try:
        while True:
            code = child.poll()
            if code is not None:
                cancelled = (
                    cancellation_seen
                    or signal_cancelled
                    or _cancel_file_requested(cancel_file)
                )
                return 130 if cancelled else code

            if not cancellation_seen and (
                    signal_cancelled or _cancel_file_requested(cancel_file)):
                cancellation_seen = True
                _mark_cancel_requested(cancel_file)
            time.sleep(_SUPERVISOR_POLL_SECONDS)
    finally:
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous_term)

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
    import ctypes
    try:
        import sip
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
    from PyQt6.QtCore import (
        QFileSystemWatcher, QObject, QProcess, QThread, QTimer,
        pyqtProperty, pyqtSignal, pyqtSlot,
    )

    _ESTIMATED_TOTAL_STEPS = 25

    class _UpdateCheckThread(QThread):
        """Runs the blocking GitHub round-trip off the GUI thread; the
        cross-thread ``done`` emit is marshalled back onto the GUI thread."""

        done = pyqtSignal("QVariantMap")

        def run(self) -> None:
            try:
                self.done.emit(update_status())
            except Exception:
                # Never let a worker-thread exception escape into Qt.
                self.done.emit({
                    "current": read_version(), "latest": "",
                    "available": False, "reachable": False,
                })

    class InstallerBridge(QObject):
        currentStepChanged = pyqtSignal()
        progressChanged = pyqtSignal()
        runningChanged = pyqtSignal()
        finished = pyqtSignal(int)
        logAppended = pyqtSignal(str)
        updateChecked = pyqtSignal("QVariantMap")

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
            self._progress_exit_code: int | None = None
            self._progress_file: str | None = None
            self._cancel_file: str | None = None
            self._update_thread: _UpdateCheckThread | None = None

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

        @pyqtProperty(str, constant=True)
        def version(self) -> str:
            """VERSION file, read synchronously with no network so the
            first paint can show it."""
            return read_version()

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
            self._progress_exit_code = None
            self.currentStepChanged.emit()
            self.progressChanged.emit()

            try:
                self._progress_file = _create_progress_file()
                self._cancel_file = _create_cancel_file()
            except OSError as exc:
                message = f"Could not create secure installer channel: {exc}"
                self._log_lines.append(message)
                self._current_step = message
                self.logAppended.emit(message)
                self.currentStepChanged.emit()
                self._finish(1)
                return

            if self._progress_file not in self._watcher.files():
                self._watcher.addPath(self._progress_file)
            self._poll.start()

            self._proc = QProcess(self)
            self._proc.setProcessChannelMode(
                QProcess.ProcessChannelMode.ForwardedChannels)
            self._proc.setWorkingDirectory(str(REPO_ROOT))
            self._proc.finished.connect(self._on_proc_finished)
            self._proc.errorOccurred.connect(self._on_proc_error)
            # Mark busy before start(): FailedToStart may be delivered as soon
            # as Qt attempts the fork/exec, and its handler must be the final
            # writer of the state rather than being overwritten below.
            self._running = True
            self.runningChanged.emit()
            self._proc.start(
                sys.executable,
                [
                    str(Path(__file__).resolve()),
                    "--supervise", action,
                    "--progress-file", self._progress_file,
                    "--cancel-file", self._cancel_file,
                ],
            )

        @pyqtSlot()
        def cancel(self) -> None:
            if not self._running:
                return
            _mark_cancel_requested(self._cancel_file)
            # Keep the supervisor (and therefore the busy state and private
            # channels) alive until the privileged transaction really exits.
            # A package manager or initramfs rebuild may need time to unwind.
            message = ("Cancelling… waiting for the current operation to stop "
                       "safely; dismiss any authentication prompt")
            if self._current_step != message:
                self._log_lines.append(message)
                self._current_step = message
                self.logAppended.emit(message)
                self.currentStepChanged.emit()

        @pyqtSlot()
        def checkForUpdates(self) -> None:
            """One-shot background update check; verdict via ``updateChecked``.
            Re-entrant calls are ignored so a double-call can't spawn two threads."""
            if self._update_thread is not None and self._update_thread.isRunning():
                return
            thread = _UpdateCheckThread(self)
            thread.done.connect(self.updateChecked)
            thread.finished.connect(thread.deleteLater)
            self._update_thread = thread
            thread.start()

        def _read_progress(self) -> None:
            progress_file = self._progress_file
            if progress_file is None:
                return
            try:
                with open(progress_file, "r", encoding="utf-8") as fh:
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

        def _handle_record(self, record: str, *, terminated: bool = True) -> None:
            if not record:
                return
            parts = record.split("\t", 1)
            head = parts[0]
            if head == DONE_MARKER:
                code = _parse_done_record(record, terminated=terminated)
                if code is not None:
                    # The CLI writes the marker in its finally block before
                    # persisting final RunTracker state and exiting. Cache the
                    # verdict, but keep the bridge busy until this run's
                    # QProcess really terminates.
                    self._progress_exit_code = code
                return
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
            self._read_progress()
            # _read_progress only turns complete lines into records; a
            # final line with no trailing newline (e.g. the process was
            # killed mid-write) would otherwise sit in _line_buf and
            # never reach the log view, hiding the most diagnostic line
            # on a failure.
            if self._line_buf:
                self._handle_record(
                    self._line_buf.rstrip("\r"), terminated=False)
                self._line_buf = ""
            if self._exit_code is None:
                # A non-zero process status wins over an earlier success
                # marker (for example, if it was killed during finalization).
                final_code = (
                    self._progress_exit_code
                    if code == 0 and self._progress_exit_code is not None
                    else code
                )
                self._finish(final_code)

        def _on_proc_error(self, error) -> None:
            if error != QProcess.ProcessError.FailedToStart:
                return
            detail = self._proc.errorString() if self._proc is not None else ""
            message = "Could not start installer supervisor"
            if detail:
                message += f": {detail}"
            self._log_lines.append(message)
            self._current_step = message
            self.logAppended.emit(message)
            self.currentStepChanged.emit()
            self._finish(1)

        def _finish(self, code: int) -> None:
            if self._exit_code is not None:
                return
            self._exit_code = code
            self._poll.stop()
            progress_file = self._progress_file
            cancel_file = self._cancel_file
            self._progress_file = None
            self._cancel_file = None
            for path in (progress_file, cancel_file):
                if path is None:
                    continue
                if path in self._watcher.files():
                    self._watcher.removePath(path)
                try:
                    os.unlink(path)
                except OSError:
                    pass
            self._progress = 1.0
            self.progressChanged.emit()
            self._running = False
            self.runningChanged.emit()
            self.finished.emit(code)

    return InstallerBridge()


def _launch_preview_pyqt() -> int:
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")

    try:
        from PyQt6.QtCore import QTimer, QUrl
        from PyQt6.QtGui import QGuiApplication
        from PyQt6.QtQml import QQmlApplicationEngine
    except ImportError:
        return -1

    # No .desktop file ships — silence the portal-registration warning.
    # Must be set before QGuiApplication is constructed.
    os.environ.setdefault("QT_NO_XDG_DESKTOP_PORTAL", "1")
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    app.setApplicationName("mac-tahoe-liquid-kde-installer")
    # A close request during an install must leave the event loop running so
    # the privileged child can stop safely and be reaped.
    app.setQuitOnLastWindowClosed(False)
    engine = QQmlApplicationEngine()
    bridge = _make_installer_bridge()
    bridge.setParent(engine)
    engine.rootContext().setContextProperty("installer", bridge)
    engine.load(QUrl.fromLocalFile(str(PREVIEW_QML)))
    roots = engine.rootObjects()
    if not roots:
        return 1
    window = roots[0]
    _enable_kwin_blur(window)
    app._installer_bridge = bridge

    # Qt's C++ event loop blocks Python signal delivery; the idle timer
    # hands control back to the interpreter so SIGINT (Ctrl+C) can land.
    shutdown = {"requested": False}

    def _on_sigint(*_):
        _request_app_quit(app, bridge, shutdown)

    def _quit_after_cancel(_code: int) -> None:
        if shutdown["requested"]:
            app.quit()

    app.lastWindowClosed.connect(
        lambda: _request_app_quit(app, bridge, shutdown))
    bridge.finished.connect(_quit_after_cancel)

    prev_sigint = signal.signal(signal.SIGINT, _on_sigint)
    wake = QTimer()
    wake.start(200)
    wake.timeout.connect(lambda: None)
    try:
        return app.exec()
    finally:
        signal.signal(signal.SIGINT, prev_sigint)


def launch_preview() -> int:
    rc = _launch_preview_pyqt()
    if rc >= 0:
        return rc

    # rc == -1 → PyQt6 missing. A bare qmlscene/qml launch would render a
    # dead window (the ``installer`` context property only exists via the
    # PyQt6 bridge), so report the missing dependency instead.
    print(
        "PyQt6 is required for the graphical installer but could not be "
        "imported.\n"
        "  Install the python-pyqt6 package for your distribution and "
        "re-run ./installer,\n"
        "  or run ./install / ./uninstall directly from a terminal.",
        file=sys.stderr,
    )
    return 1


def dump_features() -> dict[str, object]:
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
        if key != "no_download"
    ]
    return {"items": items, "config_path": str(CONFIG_FILE)}


def save_features(payload: dict[str, object]) -> dict[str, object]:
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


def update_status() -> dict[str, object]:
    """Mirror the CLI's ``--check-update`` verdict via the same engine
    pieces so GUI and CLI never disagree. Network failures and the
    MAC_TAHOE_NO_UPDATE_CHECK opt-out resolve to ``reachable=False``
    rather than raising — a flaky GitHub must never break the window."""
    current = read_version()
    latest = fetch_latest_release()
    if latest is None:
        return {
            "current": current,
            "latest": "",
            "available": False,
            "reachable": False,
        }
    return {
        "current": current,
        "latest": latest,
        "available": parse_semver(latest) > parse_semver(current),
        "reachable": True,
    }


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
    parser.add_argument(
        "--check-update",
        action="store_true",
        help="Print the update verdict as JSON (for the update banner).",
    )
    parser.add_argument(
        "--supervise",
        choices=sorted(_ACTION_COMMANDS),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--progress-file", help=argparse.SUPPRESS)
    parser.add_argument("--cancel-file", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.supervise:
        if not args.progress_file or not args.cancel_file:
            print(
                "internal supervisor requires progress and cancel files",
                file=sys.stderr,
            )
            return 2
        return _supervise_action(
            args.supervise, args.progress_file, args.cancel_file)

    if args.launch:
        payload = launch_action(args.launch)
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if payload["ok"] else 1

    if args.dump_features:
        print(json.dumps(dump_features(), ensure_ascii=False))
        return 0

    if args.check_update:
        print(json.dumps(update_status(), ensure_ascii=False))
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
