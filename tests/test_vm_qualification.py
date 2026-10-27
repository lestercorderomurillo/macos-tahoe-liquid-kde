"""Failure controls for the real desktop qualification harness."""
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


def load(name):
    path = Path(__file__).parent / 'vm' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = load('desktop_probe')
qualify = load('qualify')


@pytest.mark.parametrize('panels', [[], [{'widgets': [], 'hiding': 'autohide'}], [
    {'widgets': ['org.kde.mac-tahoe-liquid-kde.launcher',
                 'org.kde.mac-tahoe-liquid-kde.trashcan',
                 'org.kde.mac.tahoe.liquid.globalmenu'], 'hiding': 'none'},
    {'widgets': ['org.kde.mac.tahoe.liquid.icontasks'], 'hiding': 'none'}]])
def test_missing_or_non_autohiding_dock_cannot_pass(panels):
    with pytest.raises(RuntimeError):
        probe.verify_panels(panels, installed=True)


def test_uninstall_rejects_remaining_project_widget():
    with pytest.raises(RuntimeError):
        probe.verify_panels([{'widgets': ['org.kde.mac-tahoe-liquid-kde.launcher']}], False)


@pytest.mark.parametrize('state', [{}, {'script': 'install', 'status': 'completed', 'exit_code': 0},
    {'script': 'uninstall', 'status': 'failed', 'exit_code': 0},
    {'script': 'uninstall', 'status': 'completed', 'exit_code': 1}])
def test_uninstall_requires_its_own_success_record(state):
    with pytest.raises(RuntimeError):
        probe.verify_last_run(state, 'uninstalled')


def test_wrong_guest_identity_prevents_any_mutation(tmp_path, monkeypatch):
    guest = qualify.Guest('debian', tmp_path)
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess([], 0, b'arch', b'')
    monkeypatch.setattr(guest, 'run', run)
    with pytest.raises(RuntimeError, match='identity'):
        guest.qualify()
    assert len(commands) == 1
    assert 'rsync' not in commands[0] and './install' not in commands[0]


def test_kubuntu_identity_checks_lts_release_and_installed_flavor(tmp_path, monkeypatch):
    guest = qualify.Guest('kubuntu', tmp_path)
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess([], 0, b'ubuntu', b'')

    monkeypatch.setattr(guest, 'run', run)
    guest.assert_identity()
    assert '2234' in guest.ssh
    assert 'test "$VERSION_ID" = 26.04' in commands[0]
    assert "dpkg-query -W -f='${Status}' kubuntu-desktop" in commands[0]
    assert 'install ok installed' in commands[0]
    assert 'QEMU' in commands[0] and 'tester' in commands[0]


@pytest.mark.parametrize('count,child', [(8, ''), (0, ''), (7, ''),
                                       (8, '<skipped/>'), (8, '<failure/>'), (8, '<error/>')])
def test_launcher_vm_probe_requires_all_cases_without_skips(tmp_path, monkeypatch, count, child):
    guest = qualify.Guest('kubuntu', tmp_path)
    phases = []
    monkeypatch.setattr(guest, 'phase', lambda *a, **kw: phases.append(a))
    data = ('<testsuites><testsuite>' + f'<testcase>{child}</testcase>' * count
            + '</testsuite></testsuites>').encode()
    monkeypatch.setattr(guest, 'run', lambda *a: subprocess.CompletedProcess([], 0, data, b''))
    if count == 8 and not child:
        guest.launcher('launcher-installed')
    else:
        with pytest.raises(RuntimeError, match='eight native launcher'):
            guest.launcher('launcher-installed')
    assert 'test_native_launcher_popup_presets' in phases[0][1]
    assert (tmp_path / 'launcher-installed.xml').read_bytes() == data


def test_failed_phase_retains_log_and_does_not_pass(tmp_path, monkeypatch):
    guest = qualify.Guest('debian', tmp_path)
    monkeypatch.setattr(guest, 'run', lambda *a, **k: subprocess.CompletedProcess([], 7, b'failure', b'details'))
    with pytest.raises(RuntimeError, match='install failed'):
        guest.phase('install', 'false')
    assert (tmp_path / 'install.log').read_bytes() == b'failuredetails'
    report = json.loads((tmp_path / 'result.json').read_text())
    assert report['status'] != 'pass'
    assert report['phases'][0]['exit_code'] == 7


def test_ssh_bus_does_not_override_openrc_desktop_discovery(tmp_path, monkeypatch):
    guest = qualify.Guest('artix', tmp_path)
    commands = []
    def run(argv, **kwargs):
        commands.append(argv)
        return subprocess.CompletedProcess(argv, 0, b'', b'')
    monkeypatch.setattr(qualify.subprocess, 'run', run)
    guest.run('true')
    import shlex
    assert shlex.split(commands[0][-1])[:2] == ['bash', '-c']
    assert shlex.split(commands[0][-1])[2].startswith('unset DBUS_SESSION_BUS_ADDRESS DISPLAY WAYLAND_DISPLAY XDG_SESSION_TYPE; ')


def test_gtk_bridge_is_loaded_after_theme_files_are_installed(tmp_path, monkeypatch):
    from steps import gtk
    for name in gtk.VARIANTS:
        (tmp_path / 'source' / name).mkdir(parents=True)
    monkeypatch.setattr(gtk, 'offline', lambda *a: tmp_path / 'source')
    monkeypatch.setattr(gtk, 'DEST_DIR', tmp_path / 'themes')
    monkeypatch.setattr(gtk, 'GTK4_DEST', tmp_path / 'gtk-4.0')
    monkeypatch.setattr(gtk, 'have', lambda *a: False)
    events = []
    monkeypatch.setattr(gtk, 'install_tree', lambda *a: events.append('copy') or True)
    monkeypatch.setattr(gtk, 'qdbus_call', lambda *a: events.append(a))
    monkeypatch.setattr(gtk, 'info', lambda *a: events.append('summary'))
    gtk.install()
    assert events == ['copy', 'copy', ('org.kde.kded6', '/kded', 'org.kde.kded6.loadModule', 'gtkconfig'), 'summary']


@pytest.mark.parametrize('color', [(0, 0, 0), (255, 255, 255), (0, 0, 0, 0)])
def test_blank_or_transparent_capture_cannot_qualify(color):
    import io
    Image = pytest.importorskip('PIL.Image')
    image = Image.new('RGBA' if len(color) == 4 else 'RGB', (640, 480), color)
    data = io.BytesIO()
    image.save(data, format='PNG')
    with pytest.raises(RuntimeError, match='blank|transparent'):
        qualify.verify_capture(data.getvalue())


def test_visible_capture_positive_control():
    import io
    Image = pytest.importorskip('PIL.Image')
    ImageDraw = pytest.importorskip('PIL.ImageDraw')
    image = Image.new('RGB', (640, 480), 'black')
    ImageDraw.Draw(image).rectangle((50, 50, 400, 300), fill='white')
    data = io.BytesIO()
    image.save(data, format='PNG')
    qualify.verify_capture(data.getvalue())
