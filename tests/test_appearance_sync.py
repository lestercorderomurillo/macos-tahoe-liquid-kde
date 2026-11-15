"""Executable state transitions for native/manual/scheduled appearance changes."""
import json
from pathlib import Path

import pytest
import theme_switch as ts


@pytest.fixture
def desktop(sandbox, monkeypatch):
    config = sandbox / '.config'
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(sandbox))
    monkeypatch.setattr(ts, 'wait_for_clock_sync', lambda **_: True)
    monkeypatch.setattr(ts, 'button_position', lambda: 'left')
    def native(mode, automatic=False):
        (config / 'kdeglobals').write_text(
            f'[General]\nColorScheme=MacTahoeLiquidKde{mode.title()}\n'
            f'[KDE]\nAutomaticLookAndFeel={str(automatic).lower()}\n')
    native('light')
    calls = []
    def apply(mode, context='user'):
        calls.append(mode)
        native(mode, ts._appearance_snapshot()['automatic'])
        return True
    monkeypatch.setattr(ts, '_apply_unlocked', apply)
    monkeypatch.setattr(ts, '_kwrite', lambda *args: True)
    return native, calls, config


def test_native_manual_overrides_auto_and_stale_timer_cannot_revert(desktop, monkeypatch):
    native, calls, _ = desktop
    monkeypatch.setattr(ts, 'detect_mode_by_time', lambda: 'light')
    assert ts.select_appearance('auto') == 0
    native('dark')
    assert ts.reconcile_appearance()
    assert ts._read_appearance_state()['preference'] == 'dark'
    assert ts.main(['scheduled']) == 0
    assert calls == ['light', 'dark']


def test_auto_crosses_both_boundaries_without_manual_command(desktop, monkeypatch):
    native, calls, _ = desktop
    monkeypatch.setattr(ts, 'detect_mode_by_time', lambda: 'light')
    assert ts.select_appearance('auto') == 0
    monkeypatch.setattr(ts, 'detect_mode_by_time', lambda: 'dark')
    assert ts.reconcile_appearance()
    assert ts.reconcile_appearance()  # own writes do not become manual intent
    monkeypatch.setattr(ts, 'detect_mode_by_time', lambda: 'light')
    assert ts.reconcile_appearance()
    assert calls == ['light', 'dark', 'light']
    assert ts._read_appearance_state()['preference'] == 'auto'


def test_native_automatic_keeps_kde_scheduler_authoritative(desktop, monkeypatch):
    native, calls, _ = desktop
    monkeypatch.setattr(ts, 'detect_mode_by_time', lambda: 'light')
    assert ts.select_appearance('light') == 0
    native('dark', automatic=True)
    assert ts.reconcile_appearance()
    assert ts.reconcile_appearance()
    assert ts._read_appearance_state()['preference'] == 'native-auto'
    native('light', automatic=True)
    assert ts.reconcile_appearance()
    assert calls == ['light', 'dark', 'light']


@pytest.mark.parametrize('source,content', [
    ('plasmarc', '[Theme]\nname=MacTahoeLiquidKde-Dark\n'),
    ('Kvantum/kvantum.kvconfig', 'theme=mac-tahoe-liquid-kdeDark\n'),
    ('gtk-3.0/settings.ini', '[Settings]\ngtk-theme-name=MacTahoeLiquidKde-Dark\n'),
])
def test_component_selection_propagates_to_desktop(desktop, source, content):
    _, calls, config = desktop
    assert ts.select_appearance('light') == 0
    target = config / source
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    assert ts.reconcile_appearance()
    assert calls == ['light', 'dark']


def test_change_during_apply_cancels_before_next_desktop_write(desktop, monkeypatch):
    native, calls, _ = desktop
    assert ts.select_appearance('light') == 0
    native('dark')
    def interrupted(mode, context='user'):
        calls.append(mode)
        if mode == 'dark':
            native('light')  # user acts while the dependent components update
            ts._APPEARANCE_GUARD.check()
            pytest.fail('superseded transition continued')
        return True
    monkeypatch.setattr(ts, '_apply_unlocked', interrupted)
    assert ts.reconcile_appearance()
    assert calls == ['light', 'dark', 'light']
    assert ts._read_appearance_state()['applied'] == 'light'
    assert ts._APPEARANCE_GUARD is None


def test_failed_transition_is_not_acknowledged(desktop, monkeypatch):
    native, calls, _ = desktop
    assert ts.select_appearance('light') == 0
    native('dark')
    monkeypatch.setattr(ts, '_apply_unlocked', lambda *a, **k: False)
    assert not ts.reconcile_appearance()
    assert ts._read_appearance_state()['applied'] == 'light'


def test_unknown_scheme_uses_actual_background_luminance(desktop):
    _, _, config = desktop
    (config / 'kdeglobals').write_text('[General]\nColorScheme=My custom palette\n'
                                     '[Colors:Window]\nBackgroundNormal=25,30,40\n')
    assert ts._appearance_snapshot()['colors'] == 'dark'


def test_transition_lock_failure_never_runs_unserialized(desktop, monkeypatch):
    monkeypatch.setattr(ts, '_theme_transition_lock_path', lambda: Path('/dev/null/lock'))
    with pytest.raises(OSError):
        ts.select_appearance('dark')
    assert desktop[1] == []


def test_native_change_invalidates_older_queued_command(desktop, monkeypatch):
    native, _, _ = desktop
    assert ts.select_appearance('light') == 0
    native('dark')
    def interrupted(mode, context='user'):
        if mode == 'dark':
            older = ts._record_appearance_request('dark', 'user')
            native('light')
            try:
                ts._APPEARANCE_GUARD.check()
            except ts._AppearanceChanged:
                current = json.loads(ts._appearance_state_path().with_name('appearance-request.json').read_text())
                assert current != older
                assert current['preference'] == 'light'
                raise
        return True
    monkeypatch.setattr(ts, '_apply_unlocked', interrupted)
    assert ts.reconcile_appearance()
    assert ts._read_appearance_state()['applied'] == 'light'


def test_stale_component_cannot_be_recorded_as_synchronized(desktop, monkeypatch):
    _, _, config = desktop
    (config / 'plasmarc').write_text('[Theme]\nname=MacTahoeLiquidKde-Dark\n')
    assert ts.select_appearance('light') == 1
    assert ts._read_appearance_state().get("applied") is None
    assert ts._read_appearance_state()["pending"] == "light"


def test_native_palette_is_followed_without_replaying_it(desktop, monkeypatch):
    native, _, config = desktop
    native('dark')
    written = []
    monkeypatch.setattr(ts, '_kwrite', lambda *args: written.append(args) or True)
    monkeypatch.setattr(ts, '_have', lambda _: True)
    monkeypatch.setattr(ts, 'apply_color_scheme', lambda _: pytest.fail('native palette replayed'))
    monkeypatch.setattr(ts, '_APPEARANCE_GUARD', ts._AppearanceGuard('dark', follow_colors=True))
    # Native selection changes after the follower took its snapshot. Neither
    # plasma-apply-colorscheme nor kwriteconfig may overwrite the newest one.
    native('light')
    assert ts.write_kde_theme_config('dark')
    assert not any('--key' in args and args[args.index('--key') + 1] == 'ColorScheme'
                   for args in written)
    assert ts._appearance_snapshot()['colors'] == 'light'


def test_timer_overlap_does_not_fail_or_interleave(desktop):
    with ts._theme_transition_lock():
        assert ts.reconcile_appearance()
    assert desktop[1] == []


def test_lookandfeel_defaults_remain_effective_after_kconfig_elides_key(desktop):
    _, _, config = desktop
    defaults = config / 'kdedefaults'
    defaults.mkdir()
    (defaults / 'plasmarc').write_text('[Theme]\nname=MacTahoeLiquidKde-Light\n')
    (config / 'plasmarc').write_text('[Theme]\nname=MacTahoeLiquidKde-Dark\n')
    previous = ts._appearance_snapshot()
    assert previous['plasma'] == 'dark'
    (config / 'plasmarc').write_text('')
    current = ts._appearance_snapshot()
    assert current['plasma'] == 'light'
    assert ts._changed_appearance(previous, current) == 'light'


def test_session_preserves_manual_choice_but_applies_changed_declarative_mode(desktop, monkeypatch):
    _, calls, _ = desktop
    monkeypatch.setattr(ts, 'detect_mode_by_time', lambda: 'light')
    assert ts.main(['session', 'light']) == 0
    assert ts.select_appearance('dark') == 0
    assert ts.main(['session', 'light']) == 0
    assert calls == ['light', 'dark']
    assert ts.main(['session', 'auto']) == 0
    assert ts._read_appearance_state()['preference'] == 'auto'
    assert calls == ['light', 'dark', 'light']
    assert ts.select_appearance('dark') == 0
    assert ts.main(['session', 'auto']) == 0
    assert calls == ['light', 'dark', 'light', 'dark']


def test_first_session_adopts_existing_manual_preference(desktop, monkeypatch):
    _, calls, _ = desktop
    assert ts.select_appearance('dark') == 0
    assert ts.main(['session', 'light']) == 0
    assert calls == ['dark']
    assert ts._read_appearance_state()['preference'] == 'dark'


def test_failed_declarative_mode_is_retried(desktop, monkeypatch):
    _, calls, _ = desktop
    assert ts.main(['session', 'light']) == 0
    apply = ts._apply_unlocked
    monkeypatch.setattr(ts, '_apply_unlocked', lambda *args, **kwargs: False)
    assert ts.main(['session', 'dark']) == 1
    monkeypatch.setattr(ts, '_apply_unlocked', apply)
    assert ts.main(['session', 'dark']) == 0
    assert ts._read_appearance_state()['preference'] == 'dark'


def test_own_palette_write_cannot_hide_a_new_gtk_selection(sandbox, monkeypatch):
    states = iter([
        {'colors': 'light', 'gnome-color-scheme': 'dark', 'automatic': False},
        {'colors': 'dark', 'gnome-color-scheme': 'light', 'automatic': False},
    ])
    monkeypatch.setattr(ts, '_appearance_snapshot', lambda: next(states))
    guard = ts._AppearanceGuard('dark')
    with pytest.raises(ts._AppearanceChanged) as change:
        guard.check()
    assert change.value.mode == 'light'
    assert ts._read_appearance_state() == {}
    request = json.loads(ts._appearance_state_path().with_name('appearance-request.json').read_text())
    assert request['preference'] == 'light'


@pytest.mark.parametrize('command,field', [
    (['kwriteconfig6', '--file', 'kdeglobals', '--group', 'General', '--key', 'ColorScheme', 'MacTahoeLiquidKdeDark'], 'colors'),
    (['gsettings', 'set', 'org.gnome.desktop.interface', 'color-scheme', 'prefer-dark'], 'gnome-color-scheme'),
])
def test_native_reversal_between_samples_supersedes_completed_write(sandbox, monkeypatch, command, field):
    import subprocess
    monkeypatch.setattr(ts, '_appearance_snapshot', lambda: {field: 'light', 'automatic': False})
    guard = ts._AppearanceGuard('dark')
    monkeypatch.setattr(ts, '_APPEARANCE_GUARD', guard)
    monkeypatch.setattr(ts.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(command, 0))
    ts._run_user(command, timeout=5)
    with pytest.raises(ts._AppearanceChanged) as change:
        guard.check()
    assert change.value.mode == 'light'


def test_native_reversal_cancels_palette_command_before_its_final_write(sandbox, monkeypatch):
    import sys
    state = sandbox / 'palette'
    state.write_text('light')
    command = sandbox / 'plasma-apply-colorscheme'
    command.write_text(
        f'#!{sys.executable}\nfrom pathlib import Path\nimport time\n'
        f'p=Path({str(state)!r})\n'
        "p.write_text('dark')\ntime.sleep(.15)\n"
        "p.write_text('light')\ntime.sleep(.3)\n"
        "p.write_text('dark')\n")
    command.chmod(0o755)
    monkeypatch.setattr(ts, '_appearance_snapshot',
                        lambda: {'colors': state.read_text(), 'automatic': False})
    monkeypatch.setattr(ts, '_APPEARANCE_GUARD', ts._AppearanceGuard('dark'))
    with pytest.raises(ts._AppearanceChanged) as change:
        ts._run_user([str(command), 'MacTahoeLiquidKdeDark'], timeout=3)
    assert change.value.mode == 'light'
    assert state.read_text() == 'light'


@pytest.mark.parametrize('cleanup_error', [False, True])
def test_widget_cleanup_restores_signal_handlers_and_defers_cancellation(sandbox, monkeypatch, cleanup_error):
    import signal
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    pending = [False]
    writes = []
    class Guard:
        def check(self):
            if pending[0]:
                raise ts._AppearanceChanged('light', False)
    guard = Guard()
    monkeypatch.setattr(ts, '_APPEARANCE_GUARD', guard)
    monkeypatch.setattr(ts, '_have', lambda _: True)
    monkeypatch.setattr(ts, '_has_session_dbus', lambda: True)
    monkeypatch.setattr(ts.time, 'sleep', lambda _: pending.__setitem__(0, True))
    def write(*args):
        if ts._APPEARANCE_GUARD is not None:
            ts._APPEARANCE_GUARD.check()
        writes.append(args[-1])
        if cleanup_error and args[-1] == 'MacTahoe':
            raise OSError('simulated cleanup write failure')
        return True
    monkeypatch.setattr(ts, '_kwrite', write)
    monkeypatch.setattr(ts, '_broadcast_widget_style_change', lambda _: True)
    try:
        if cleanup_error:
            with pytest.raises(OSError):
                ts.cycle_widget_style_live('MacTahoe')
        else:
            assert ts.cycle_widget_style_live('MacTahoe')
        assert writes == ['Breeze', 'MacTahoe']
        assert ts._APPEARANCE_GUARD is guard
        assert all(signal.getsignal(sig) is handler for sig, handler in handlers.items())
        with pytest.raises(ts._AppearanceChanged):
            guard.check()
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)



def test_successful_native_palette_apply_is_not_replayed(desktop, monkeypatch):
    native, _, _ = desktop
    monkeypatch.setattr(ts, '_have', lambda _: True)
    def apply_scheme(scheme):
        native('light')  # a newer native selection after the requested apply
        return True
    monkeypatch.setattr(ts, 'apply_color_scheme', apply_scheme)
    writes = []
    monkeypatch.setattr(ts, '_kwrite', lambda *args: writes.append(args) or True)
    assert ts.write_kde_theme_config('dark', force_color_reload=False)
    assert not any('--key' in args and args[args.index('--key') + 1] == 'ColorScheme'
                   for args in writes)
    assert ts._appearance_snapshot()['colors'] == 'light'


def test_selection_after_final_guard_is_not_acknowledged_as_our_write(desktop, monkeypatch):
    native, calls, _ = desktop
    assert ts.select_appearance('light') == 0
    original_snapshot = ts._appearance_snapshot
    pending_native = [False]
    def apply(mode, context='user'):
        calls.append(mode)
        native(mode)
        if mode == 'dark':
            pending_native[0] = True
        return True
    def snapshot():
        if pending_native[0] and ts._APPEARANCE_GUARD is None:
            pending_native[0] = False
            native('light')
        return original_snapshot()
    monkeypatch.setattr(ts, '_apply_unlocked', apply)
    monkeypatch.setattr(ts, '_appearance_snapshot', snapshot)
    assert ts.select_appearance('dark') == 0
    assert ts.reconcile_appearance()
    assert calls == ['light', 'dark', 'light']
    assert ts._read_appearance_state()['preference'] == 'light'
    assert ts._read_appearance_state()['applied'] == 'light'


def test_completed_gsettings_write_invalidates_cache_before_database_flush(sandbox, monkeypatch):
    import subprocess
    config = sandbox / '.config'
    (config / 'dconf').mkdir(exist_ok=True)
    (config / 'dconf/user').write_bytes(b'unchanged on-disk database identity')
    values = {'color-scheme': 'prefer-dark', 'gtk-theme': 'MacTahoeLiquidKde-Dark'}
    monkeypatch.setattr(ts, '_xdg_config', lambda: config)
    monkeypatch.setattr(ts, '_GNOME_APPEARANCE_CACHE', (None, {}))
    monkeypatch.setattr(ts, '_have', lambda _: True)
    def run(command, **kwargs):
        if command[1] == 'set':
            values[command[3]] = command[4]
        return subprocess.CompletedProcess(command, 0, repr(values[command[3]]), '')
    monkeypatch.setattr(ts.subprocess, 'run', run)
    monkeypatch.setattr(ts, '_appearance_snapshot',
                        lambda: ts._gnome_appearance() | {'automatic': False})
    guard = ts._AppearanceGuard('light')
    monkeypatch.setattr(ts, '_APPEARANCE_GUARD', guard)
    ts._run_user(['gsettings', 'set', 'org.gnome.desktop.interface', 'color-scheme', 'prefer-light'], timeout=5)
    guard.check()
    assert guard.previous['gnome-color-scheme'] == 'light'


def test_delayed_kde_gtk_file_echo_cannot_reverse_newer_native_palette(sandbox, monkeypatch):
    states = iter([
        {'colors': 'light', 'gnome-color-scheme': 'light', 'gtk': 'light', 'automatic': False},
        {'colors': 'light', 'gnome-color-scheme': 'light', 'gtk': 'dark', 'automatic': False},
        {'colors': 'light', 'gnome-color-scheme': 'light', 'gtk': 'light', 'automatic': False},
    ])
    monkeypatch.setattr(ts, '_appearance_snapshot', lambda: next(states))
    guard = ts._AppearanceGuard('light', follow_colors=True)
    guard.check()
    guard.check()
    assert guard.previous['gtk'] == 'light'
