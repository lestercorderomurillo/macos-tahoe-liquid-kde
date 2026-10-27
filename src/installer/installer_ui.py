#!/usr/bin/env python3
"""Graphical wizard and supervised privileged installation backend."""

from __future__ import annotations

import argparse
import errno
import json
import os
import pwd
import re
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
from launcher_defaults import edition_name
from cli import (
    ALL_FEATURES, DEFAULT_FEATURES, FEATURE_DESC,
    fetch_latest_release, parse_semver,
)
from log import DONE_MARKER, STATUS_MARKER
from localization import (
    effective_language, feature_label, get_language, language_options, set_language, translate, tr,
)


_ACTION_COMMANDS = {
    "install": "sudo ./src/scripts/installer_backend.py install",
    "uninstall": "sudo ./src/scripts/installer_backend.py uninstall",
    "preflight": "sudo ./src/scripts/installer_backend.py install --preflight",
}

_SUPERVISOR_POLL_SECONDS = 0.05


def _create_private_run_file(prefix: str) -> str:
    """Create one private control channel before privilege escalation."""
    fd, path = tempfile.mkstemp(prefix=prefix, dir="/tmp")
    try:
        os.fchmod(fd, 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise OSError(errno.EPERM, tr('secure run file is not regular'))
        if info.st_uid != os.geteuid():
            raise OSError(errno.EPERM, tr('secure run file has the wrong owner'))
        if info.st_nlink != 1:
            raise OSError(errno.EPERM, tr('secure run file has extra links'))
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
            raise OSError(errno.EPERM, tr('run file is not regular'))
        if (info.st_uid != os.geteuid() or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o600):
            raise OSError(
                errno.EPERM, tr('run file owner, mode, or link count changed'))
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
                raise OSError(errno.EIO, tr('short cancellation-token write'))
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
        cancel_file: str | None = None,
        choices: dict | None = None) -> str:
    base = _ACTION_COMMANDS[action]
    target = base[len("sudo "):] if base.startswith("sudo ") else base
    if choices is not None and action in ("install", "uninstall"):
        from installer_choices import validate
        target += " --wizard-options " + shlex.quote(json.dumps(validate(choices)))

    headless_pairs = [f"MTTKDE_LANGUAGE={shlex.quote(effective_language(get_language()))}"]
    if headless:
        if progress_file is None or cancel_file is None:
            raise ValueError(
                tr('headless installer launch requires progress and cancel files'))
        headless_pairs += [
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
    if headless:
        askpass = shlex.quote(str(Path(__file__).with_name("askpass.py")))
        return f"SUDO_ASKPASS={askpass} sudo -A {prefix}{target}"
    return f"sudo {prefix}{target}"


def _supervise_action(action: str, progress_file: str,
                      cancel_file: str, choices: dict | None = None) -> int:
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
        print(tr('Could not isolate privileged installer supervisor'),
              file=sys.stderr)
        return 1
    if _cancel_file_requested(cancel_file):
        return 130

    shell_cmd = escalated_command_for_action(
        action,
        headless=True,
        progress_file=progress_file,
        cancel_file=cancel_file,
        **({"choices": choices} if choices is not None else {}),
    )
    try:
        child = subprocess.Popen(
            ["bash", "-lc", shell_cmd],
            cwd=str(REPO_ROOT),
        )
    except OSError as exc:
        print(tr('Could not start privileged installer: {exc}', exc=exc), file=sys.stderr)
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
            tr('installer UI must be launched from a regular desktop user (or via sudo from that user session).'),
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

    class _UpdateInstallThread(QThread):
        def run(self) -> None:
            from cli import auto_update_and_reexec
            auto_update_and_reexec([], prog="installer")

    class InstallerBridge(QObject):
        currentStepChanged = pyqtSignal()
        progressChanged = pyqtSignal()
        runningChanged = pyqtSignal()
        finished = pyqtSignal(int)
        logAppended = pyqtSignal(str)
        updateChecked = pyqtSignal("QVariantMap")
        updateReturned = pyqtSignal()
        languageChanged = pyqtSignal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self._proc: QProcess | None = None
            self._current_step = ""
            self._step_index = 0
            self._progress = 0.0
            self._estimated_total = _ESTIMATED_TOTAL_STEPS
            self._running = False
            self._log_lines: list[str] = []
            self._read_offset = 0
            self._line_buf = ""
            self._exit_code: int | None = None
            self._progress_exit_code: int | None = None
            self._progress_file: str | None = None
            self._cancel_file: str | None = None
            self._update_thread: _UpdateCheckThread | None = None
            self._update_install_thread = None
            self._language = get_language()
            self._choices = None

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
        def editionName(self) -> str:
            return edition_name()

        @pyqtProperty(str, constant=True)
        def version(self) -> str:
            """VERSION file, read synchronously with no network so the
            first paint can show it."""
            return read_version()

        @pyqtProperty(str, notify=languageChanged)
        def language(self) -> str:
            return self._language

        @pyqtProperty("QVariantList", constant=True)
        def languages(self):
            return language_options("en")

        @pyqtSlot(str, result=str)
        def translate(self, message: str) -> str:
            return translate(message, self._language)

        @pyqtSlot(str, result=bool)
        def setLanguage(self, code: str) -> bool:
            if code == self._language:
                return True
            if not set_language(code):
                return False
            self._language = code
            self.languageChanged.emit()
            return True

        @pyqtSlot(result=str)
        def logTail(self) -> str:
            return "\n".join(self._log_lines[-200:])

        @pyqtSlot("QVariantMap")
        def setChoices(self, choices):
            if self._running:
                return
            from installer_choices import validate
            self._choices = validate(choices)

        @pyqtSlot(str)
        def start(self, action: str) -> None:
            if self._running or action not in _ACTION_COMMANDS:
                return
            from cli import _estimate_install_steps, _estimate_uninstall_steps, _theme_is_already_installed
            from installer_choices import features
            selected_features = features(self._choices, DEFAULT_FEATURES,
                                         existing_install=_theme_is_already_installed()) if self._choices else DEFAULT_FEATURES
            self._estimated_total = (_estimate_uninstall_steps(DEFAULT_FEATURES) if action == "uninstall"
                                     else _estimate_install_steps(selected_features))
            self._log_lines.clear()
            self._current_step = translate("Starting…", self._language)
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
                message = tr("Could not create secure installer channel: {error}", error=exc)
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
                QProcess.ProcessChannelMode.MergedChannels)
            self._proc.readyReadStandardOutput.connect(self._read_output)
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
                    *(["--wizard-options", json.dumps(self._choices)]
                      if self._choices is not None else []),
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
            message = translate(
                "Cancelling… waiting for the current operation to stop safely; "
                "dismiss any authentication prompt",
                self._language,
            )
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
            self._update_thread = thread
            thread.start()

        @pyqtSlot()
        def updateInstaller(self):
            if self._running or (self._update_install_thread and self._update_install_thread.isRunning()):
                return
            self._update_install_thread = _UpdateInstallThread(self)
            self._update_install_thread.finished.connect(self.updateReturned)
            self._update_install_thread.start()

        def waitForUpdateWorkers(self):
            for thread in (self._update_thread, self._update_install_thread):
                if thread is not None:
                    thread.wait()

        def _read_output(self) -> None:
            if self._proc is None:
                return
            output = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
            for line in re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", output).splitlines():
                self._log_lines.append(line)
                self.logAppended.emit(line)
            if len(self._log_lines) > 2000:
                del self._log_lines[:-1000]

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
            title = parts[1].split("\t", 1)[0] if len(parts) > 1 else head
            self._log_lines.append(title)
            if len(self._log_lines) > 2000:
                del self._log_lines[:1000]
            self.logAppended.emit(title)
            self._current_step = title
            if head == STATUS_MARKER:
                self.currentStepChanged.emit()
                return
            self._step_index += 1
            self._progress = min(
                self._step_index / max(1, self._estimated_total), 0.95)
            self.currentStepChanged.emit()
            self.progressChanged.emit()

        def _on_proc_finished(self, code: int, _status) -> None:
            self._read_output()
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
            message = tr("Could not start installer supervisor")
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


def _launch_preview_pyqt(uninstall=False) -> int:
    try:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication
        from wizard_window import InstallerWindow
    except ImportError:
        return -1
    os.environ.setdefault("QT_NO_XDG_DESKTOP_PORTAL", "1")
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("mac-tahoe-liquid-kde-installer")
    app.setQuitOnLastWindowClosed(False)
    bridge = _make_installer_bridge()
    window = InstallerWindow(bridge, uninstall=uninstall)
    bridge.setParent(window)
    app._installer_bridge = bridge
    app._installer_window = window
    window.show()
    bridge.checkForUpdates()
    app.aboutToQuit.connect(bridge.waitForUpdateWorkers)

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


def launch_preview(uninstall=False) -> int:
    rc = _launch_preview_pyqt(True) if uninstall else _launch_preview_pyqt()
    if rc >= 0:
        return rc

    # rc == -1 → PyQt6 missing. A bare qmlscene/qml launch would render a
    # dead window (the ``installer`` context property only exists via the
    # PyQt6 bridge), so report the missing dependency instead.
    print(
        tr('PyQt6 is required for the graphical installer but could not be imported.\n  Install the python-pyqt6 package for your distribution and re-run ./installer.'),
        file=sys.stderr,
    )
    return 1


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
    parser = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name or "installer",
        description=__doc__,
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
    parser.add_argument("--uninstall", action="store_true", help="Open the graphical uninstaller.")
    parser.add_argument("--wizard-options", help=argparse.SUPPRESS)
    parser.add_argument("--progress-file", help=argparse.SUPPRESS)
    parser.add_argument("--cancel-file", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    rc = drop_root_to_invoking_user()
    if rc != 0:
        return rc

    if args.supervise:
        if not args.progress_file or not args.cancel_file:
            print(
                tr('internal supervisor requires progress and cancel files'),
                file=sys.stderr,
            )
            return 2
        return _supervise_action(
            args.supervise, args.progress_file, args.cancel_file,
            json.loads(args.wizard_options) if args.wizard_options else None)

    if args.check_update:
        print(json.dumps(update_status(), ensure_ascii=False))
        return 0

    if not args.uninstall:
        from cli import auto_update_and_reexec
        auto_update_and_reexec([], prog="installer")

    return launch_preview(True) if args.uninstall else launch_preview()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
