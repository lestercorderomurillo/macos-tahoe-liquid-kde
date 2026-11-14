"""Progress must describe real work and survive process/stream boundaries."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from installer_lock import installer_lock, InstallerBusy
from progress_model import ProgressModel


def test_transaction_lock_excludes_other_process_and_survives_failed_attempt(tmp_path):
    path = tmp_path / 'transaction.lock'
    script = 'from installer_lock import installer_lock; import sys\nwith installer_lock(sys.argv[1]): print("acquired")'
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src/scripts'))
    with installer_lock(path):
        result = subprocess.run([sys.executable, '-c', script, str(path)], env=env, capture_output=True, text=True)
        assert result.returncode != 0 and 'Another installation or removal' in result.stderr
        with pytest.raises(InstallerBusy):
            with installer_lock(path):
                pytest.fail('a rejected contender must not release the first lock')
    result = subprocess.run([sys.executable, '-c', script, str(path)], env=env, capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout.strip() == 'acquired'


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'permissions', 'fifo'])
def test_transaction_lock_rejects_unsafe_file_without_modifying_it(tmp_path, kind):
    target = tmp_path / 'target'
    target.write_text('keep')
    path = tmp_path / 'lock'
    if kind == 'symlink': path.symlink_to(target)
    elif kind == 'hardlink': os.link(target, path)
    elif kind == 'fifo': os.mkfifo(path, 0o600)
    else: path.write_text('keep'); path.chmod(0o666)
    with pytest.raises(OSError):
        with installer_lock(path): pytest.fail('unsafe lock accepted')
    assert target.read_text() == 'keep'


def test_summary_failure_warnings_and_unrun_phases_are_not_success():
    model = ProgressModel()
    model.accept({'kind': 'phase', 'id': 'system', 'state': 'running'})
    model.accept({'kind': 'phase', 'id': 'system', 'state': 'done'})
    model.accept({'kind': 'phase', 'id': 'build', 'state': 'running'})
    model.accept({'kind': 'build', 'id': 'plasmoids', 'state': 'failed'})
    model.accept({'kind': 'warning', 'message': 'Optional download skipped'})
    model.finish(1)
    model.accept({'kind': 'phase', 'id': 'build', 'state': 'done'})
    assert model.phases['system']['state'] == 'done'
    assert model.phases['build']['state'] == 'failed'
    assert model.phases['install']['state'] == 'pending'
    assert model.failed_label() == 'Launcher and Dock'
    assert model.warnings == ['Optional download skipped']


@pytest.fixture
def bridge():
    from PyQt6.QtCore import QCoreApplication
    from installer_ui import _make_installer_bridge
    app = QCoreApplication.instance() or QCoreApplication([])
    instance = _make_installer_bridge()
    yield instance
    instance._finish(130)
    app.processEvents()


def test_output_decoder_retains_split_utf8_lines_and_full_log(bridge):
    class Output:
        data = b''
        def readAllStandardOutput(self):
            data, self.data = self.data, b''
            return data
    proc = Output()
    bridge._proc = proc
    emitted = []
    bridge.logAppended.connect(emitted.append)
    data = '✓ Building\n'.encode()
    for byte in data:
        proc.data = bytes([byte]); bridge._read_output()
    assert emitted == ['✓ Building']
    for i in range(2100):
        proc.data = f'line {i}\n'.encode(); bridge._read_output()
    proc.data = b'last fragment'; bridge._read_output(final=True)
    assert '✓ Building\nline 0\n' in bridge.logText()
    assert bridge.logText().endswith('last fragment\n')
    assert len(bridge._log_lines) == 2000
    assert 'line 0\n' not in bridge.logTail()


def test_protocol_does_not_duplicate_stdout_or_count_status_as_steps(bridge):
    bridge._handle_record('1\tPreflight\tPreflight')
    before = bridge.progress
    bridge._handle_record('__STATUS__\tGenerating icons: 20/100')
    bridge._handle_record('1\tPreflight\tPreflight')
    bridge._handle_record('junk\tignored')
    bridge._handle_record('9' * 5000 + '\tignored')
    bridge._handle_record('__EVENT__\t' + json.dumps({'kind': 'phase', 'id': 'build', 'state': 'running'}))
    assert bridge.progress == before and bridge._step_index == 1
    assert bridge.logText() == ''
    assert bridge.summary.active == 'build'


def test_late_process_callbacks_cannot_finish_replacement_run(bridge):
    old, current = object(), object()
    bridge._proc = current
    seen = []
    bridge._from_process(old, seen.append, 'stale')
    bridge._from_process(current, seen.append, 'current')
    assert seen == ['current']


def test_reentrant_start_is_blocked_until_completion_handlers_return(bridge):
    bridge._running = True
    bridge.runningChanged.connect(lambda: bridge.start('install'))
    bridge._finish(0)
    assert not bridge.running and bridge._proc is None


@pytest.mark.parametrize('done,crash', [(False, False), (True, True)])
def test_incomplete_or_crashed_process_never_reports_success(bridge, done, crash):
    from PyQt6.QtCore import QProcess
    bridge._requires_done = True
    if done: bridge._handle_record('__DONE__\t0')
    seen = []
    bridge.finished.connect(seen.append)
    bridge._on_proc_finished(0, QProcess.ExitStatus.CrashExit if crash else QProcess.ExitStatus.NormalExit)
    assert seen == [1]


def test_configured_channel_reset_preserves_already_observed_startup_warning(monkeypatch, tmp_path, bridge):
    import log
    path = tmp_path / 'progress'
    path.touch(mode=0o600)
    monkeypatch.setattr(log, 'PROGRESS_FILE', str(path))
    monkeypatch.setattr(log, '_CONFIGURED_PROGRESS_FILE', str(path))
    bridge._progress_file = str(path)
    log.warn('Startup warning')
    bridge._read_progress()
    offset = bridge._read_offset
    log.progress_reset()
    log.progress_event('phase', id='system', state='running')
    log.progress_done(0)
    bridge._read_progress()
    assert bridge._read_offset > offset
    assert bridge.summary.warnings == ['Startup warning']
    assert bridge.summary.active == 'system'
    assert bridge._progress_exit_code == 0


def test_background_warning_does_not_create_an_unobserved_progress_file(monkeypatch, tmp_path):
    import log
    path = tmp_path / 'unused-progress'
    monkeypatch.setattr(log, '_CONFIGURED_PROGRESS_FILE', None)
    monkeypatch.setattr(log, 'PROGRESS_FILE', str(path))
    log.warn('Background service warning')
    assert not path.exists()


def test_log_storage_failure_keeps_gui_running_and_retains_diagnostic(bridge):
    class FullDisk:
        def write(self, _text): raise OSError('No space left on device')
    bridge._log_file = FullDisk()
    bridge._running = True
    bridge._append_log('Compiler failed')
    bridge._append_log('Diagnostic details')
    assert bridge.running
    assert 'Only the latest output is retained' in bridge.logText()
    assert bridge.logText().endswith('Compiler failed\nDiagnostic details')
    assert len(bridge.summary.warnings) == 1


def test_backend_lock_precedes_any_install_work(monkeypatch, tmp_path):
    import installer_backend
    from types import SimpleNamespace
    path = tmp_path / 'lock'
    monkeypatch.setattr(installer_backend, 'os', SimpleNamespace(geteuid=lambda: 0))
    monkeypatch.setattr(installer_backend, 'installer_lock', lambda: installer_lock(path))
    calls = []
    monkeypatch.setattr(installer_backend, 'run_install', lambda args: calls.append(args) or 0)
    with installer_lock(path):
        assert installer_backend.main(['install']) == 2
        assert not calls
    assert installer_backend.main(['install']) == 0
    assert calls == [[]]


@pytest.mark.parametrize('declined', [False, True])
def test_backend_exception_or_declined_confirmation_never_records_success(monkeypatch, sandbox, declined):
    import cli
    import state
    monkeypatch.setattr(cli, '_require_root_and_drop_to_user', lambda *_: True)
    monkeypatch.setattr(cli, '_theme_is_already_installed', lambda: False)
    monkeypatch.setattr(cli, 'load_features', lambda: dict(cli.DEFAULT_FEATURES))
    monkeypatch.setattr(cli, 'export_env', lambda *_: None)
    monkeypatch.setattr(cli, 'banner', lambda *_: None)
    monkeypatch.setattr(cli, 'confirm', lambda *_: not declined)
    monkeypatch.setattr(cli, 'check_for_updates', lambda **_: False)
    def broken(_features): raise RuntimeError('Unexpected backend failure')
    monkeypatch.setattr(cli, '_run_install_body', broken)
    codes = []
    monkeypatch.setattr(cli, 'progress_done', codes.append)
    if declined:
        assert cli.run_install([]) == 130
    else:
        with pytest.raises(RuntimeError, match='Unexpected backend failure'):
            cli.run_install([])
    record = json.loads(state.last_run_file().read_text())
    assert record['status'] == ('aborted' if declined else 'failed')
    assert codes == [130 if declined else 1]


def test_install_cannot_start_while_checkout_update_is_running(bridge):
    from types import SimpleNamespace
    bridge._update_install_thread = SimpleNamespace(isRunning=lambda: True)
    bridge.start('install')
    assert not bridge.running and bridge._proc is None


def test_log_export_is_private_and_failed_write_preserves_existing_file(bridge, tmp_path, monkeypatch):
    from PyQt6 import QtCore
    bridge._append_log('Complete diagnostic')
    path = tmp_path / 'installation.log'
    bridge.saveLog(str(path))
    assert path.read_text() == 'Complete diagnostic\n'

    assert path.stat().st_mode & 0o777 == 0o600
    original = QtCore.QSaveFile
    def failed_output(name):
        result = original(name)
        result.write = lambda _data: -1
        return result
    monkeypatch.setattr(QtCore, 'QSaveFile', failed_output)
    bridge._append_log('New output')
    with pytest.raises(OSError):
        bridge.saveLog(str(path))
    assert path.read_text() == 'Complete diagnostic\n'


def test_cancel_during_channel_setup_prevents_backend_launch(bridge, monkeypatch):
    import installer_ui
    from PyQt6.QtCore import QProcess
    original = installer_ui._create_progress_file
    def early_cancel():
        path = original()
        bridge.cancel()
        return path
    monkeypatch.setattr(installer_ui, '_create_progress_file', early_cancel)
    monkeypatch.setattr(QProcess, 'start', lambda *_: pytest.fail('Cancelled run launched'))
    codes = []
    bridge.finished.connect(codes.append)
    bridge.start('install')
    assert codes == [130] and not bridge.running
    assert bridge._progress_file is None and bridge._cancel_file is None


def test_late_progress_does_not_replace_cancellation_message(bridge):
    bridge._language = 'en'
    bridge._running = True
    bridge.cancel()
    message = bridge.currentStep
    bridge._handle_record('__STATUS__\tBuilding more components')
    bridge.cancel()
    assert bridge.currentStep == message and bridge.statusMessage == message
    assert bridge.logText().count(message) == 1
