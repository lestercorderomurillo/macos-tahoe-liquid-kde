"""Optional apps: consent, desktop discovery and failure containment (no installs)."""
import json
import re
from types import SimpleNamespace

import pytest
import dock_apps as apps
import distro
from installer_choices import defaults, features, validate


def desktop(root, name, extra=""):
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text("[Desktop Entry]\nType=Application\nName=Existing\nExec=true\n" + extra)


def test_catalog_matches_every_plasma_entry_point(offline):
    paths = [offline / 'layouts/mac-tahoe.js', offline / 'layouts/migrate-dock-preset.js',
             *offline.glob('look-and-feel/*/contents/layouts/org.kde.plasma.desktop-layout.js')]
    for path in paths:
        catalog = json.loads(re.search(r'var dockApplications = (\[.*?\]);', path.read_text(), re.S)[1])
        assert catalog == list(apps.CANDIDATES.values())


def test_discovery_user_masks_and_flatpak_exports(tmp_path, monkeypatch):
    user, system = tmp_path / 'user', tmp_path / 'system'
    desktop(user, 'org.kde.gwenview.desktop', 'Hidden=true\n')
    desktop(system, 'org.kde.gwenview.desktop')
    desktop(system, 'org.gnome.Loupe.desktop')
    desktop(system, 'com.vixalien.sticky.desktop')
    desktop(system, 'org.kde.elisa.desktop', 'TryExec=nonexistent-test-binary\n')
    desktop(system, 'org.kde.haruna.desktop', 'NoDisplay=true\n')
    found = apps.installed_apps([user, system])
    assert found['photos'] == found['notes'] == 'Existing'
    assert not found['music'] and not found['video']
    (system / 'org.gnome.Loupe.desktop').unlink()
    assert not apps.installed_apps([user, system])['photos']


@pytest.mark.parametrize('value', [['mail','mail'], ['--bad'], 'mail', [None], {'mail': True}])
def test_invalid_selection(value):
    with pytest.raises(ValueError):
        validate({'dock_apps': value})


def test_opt_in_and_keep_layout(monkeypatch):
    calls=[]
    monkeypatch.setattr(apps, 'pkg_install', lambda *a: calls.append(a))
    apps.install_selected(defaults())
    apps.install_selected(defaults() | {'dock':False, 'dock_apps':['mail']})
    assert calls == []
    assert not features(defaults(), {'apps':True})['apps']
    assert features({'reset_layout':False, 'dock_apps':['mail']}, {}, existing_install=True)['apps']


def test_recheck_existing_and_failure_continues(monkeypatch):
    monkeypatch.setattr(apps, 'installed_apps', lambda: {'notes':'Sticky'})
    monkeypatch.setattr(apps, 'recommendation', lambda key, source: (key, key))
    calls=[]; warnings=[]
    monkeypatch.setattr(apps, 'pkg_install', lambda pkg: calls.append(pkg) or False)
    monkeypatch.setattr(apps, 'warn', warnings.append)
    apps.install_selected({'dock_apps':['notes','mail','calendar']})
    assert calls == ['mail','calendar']
    assert len(warnings) == 2


def test_package_success_without_desktop_is_pending(monkeypatch):
    monkeypatch.setattr(apps, 'installed_apps', lambda: {})
    monkeypatch.setattr(apps, 'recommendation', lambda *a: ('Mail','thunderbird'))
    monkeypatch.setattr(apps, 'pkg_install', lambda *a: True)
    warnings=[]
    monkeypatch.setattr(apps, 'warn', warnings.append)
    apps.install_selected({'dock_apps':['mail']})
    assert len(warnings) == 1


@pytest.mark.parametrize('remote,allow,ready', [
    ('',False,False), ('',True,True),
    ('flathub\thttps://dl.flathub.org/repo/\n',False,True),
    ('flathub\thttps://untrusted.invalid/repo/\n',True,False),
])
def test_flatpak_remote_consent(monkeypatch, remote, allow, ready):
    monkeypatch.setattr(apps.shutil, 'which', lambda cmd: '/usr/bin/' + cmd)
    calls=[]
    def run(*args):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=remote if args[0]=='remotes' else '')
    monkeypatch.setattr(apps, '_flatpak', run)
    assert apps._prepare_flatpak(allow) is ready
    adds = [cmd for cmd in calls if cmd[0]=='remote-add']
    assert bool(adds) == (not remote and allow)
    assert all('--user' in cmd for cmd in calls)


def test_flatpak_never_runs_as_root(monkeypatch):
    calls=[]
    monkeypatch.setattr(apps, 'run_user', lambda args, **kwargs: calls.append(args))
    apps._flatpak('remotes','--user')
    assert calls == [['flatpak','remotes','--user']]


@pytest.mark.parametrize('family,category,expected', [
    ('arch','calendar',('Merkuro','merkuro')),
    ('debian','calendar',('KOrganizer','korganizer')),
    ('fedora','calendar',('KOrganizer','korganizer')),
    ('opensuse','mail',('Thunderbird','MozillaThunderbird')),
    ('unknown','mail',None),
])
def test_native_mappings(monkeypatch, family, category, expected):
    monkeypatch.setattr(distro, 'current_distro', lambda: family)
    monkeypatch.setattr(distro, '_compatibility_parents', lambda: ())
    assert distro.dock_app_package(category) == expected


def test_cachyos_inherits_arch(monkeypatch):
    monkeypatch.setattr(distro, 'current_distro', lambda:'cachyos')
    monkeypatch.setattr(distro, '_compatibility_parents', lambda:('arch',))
    assert distro.dock_app_package('calendar') == ('Merkuro','merkuro')


def test_dock_apps_dialog_consent_and_cancel(repo, tmp_path):
    import os
    import subprocess
    import sys
    script = r'''
import sys
from pathlib import Path
sys.path[:0] = [str(Path.cwd()/'src/scripts'), str(Path.cwd()/'src/installer')]
from PyQt6.QtWidgets import QApplication, QDialog, QComboBox, QDialogButtonBox
from PyQt6.QtCore import QTimer
from installer_ui import _make_installer_bridge
from wizard_window import InstallerWindow, CheckOption
import cli, dock_apps
cli._theme_is_already_installed = lambda: True
dock_apps.installed_apps = lambda: {'notes':'Sticky', 'photos':'Loupe', 'video':'Showtime'}
dock_apps.recommendation = lambda category, source: (category.title(), category + '.package')
app = QApplication([])
bridge = _make_installer_bridge()
bridge._language = 'en'
window = InstallerWindow(bridge)
window.page = 'layout'
window.render()
assert window.choices['dock_apps'] == []
errors=[]
def interact(accept):
    dialog = app.activeModalWidget()
    try:
        assert isinstance(dialog, QDialog)
        assert not dialog.findChild(CheckOption,'dock-app-notes').isEnabled()
        assert not dialog.findChild(CheckOption,'dock-app-photos').isEnabled()
        appearance = dialog.findChild(QComboBox, 'dock-appearance')
        assert appearance.currentData() == 'auto'
        appearance.setCurrentIndex(appearance.findData('macos'))
        mail = dialog.findChild(CheckOption,'dock-app-mail')
        assert not mail.isChecked()
        mail.click()
        dialog.findChild(QComboBox,'dock-apps-source').setCurrentIndex(1)
        remote = dialog.findChild(CheckOption,'dock-add-flathub')
        assert remote.isVisible() and not remote.isChecked()
        remote.click()
        assert dialog.height() < 700
    except BaseException as error:
        errors.append(error)
    dialog.accept() if accept else dialog.reject()
QTimer.singleShot(0, lambda: interact(False))
window.edit_dock_apps()
assert window.choices['dock_apps'] == []
assert window.choices['dock_appearance'] == 'auto'
assert window.choices['dock_apps_source'] == 'native'
assert not window.choices['dock_add_flathub']
QTimer.singleShot(0, lambda: interact(True))
window.edit_dock_apps()
assert not errors, errors
assert window.choices['dock_apps'] == ['mail']
assert window.choices['dock_appearance'] == 'macos'
assert window.choices['dock_apps_source'] == 'flatpak'
assert window.choices['dock_add_flathub']
assert 'Mail' in window.dock_app_summary() and 'Flatpak' in window.dock_app_summary()
window.choices['dock']=False
assert window.dock_app_summary() == 'Use installed apps only'
window.close()
'''
    env = os.environ | {'QT_QPA_PLATFORM':'offscreen', 'XDG_CONFIG_HOME':str(tmp_path),
                        'MAC_TAHOE_NO_UPDATE_CHECK':'true', 'PYTHONDONTWRITEBYTECODE':'1'}
    result = subprocess.run([sys.executable, '-c', script], cwd=repo, env=env,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
