#!/usr/bin/env python3
"""Qualify declarative session defaults without restarting open VM applications."""
import json
import os
from pathlib import Path
import subprocess
import time

if Path('/sys/class/dmi/id/product_name').read_text().strip() != 'MTTKDE release capture':
    raise SystemExit('This probe requires the disposable capture VM')
home = Path.home()
probe = home / 'appearance-probe'
state_path = home / '.local/state/mac-tahoe-liquid-kde/appearance.json'
identities = {}
for item in json.loads((probe / 'processes.json').read_text()):
    path = Path('/proc') / str(item['pid']) / 'stat'
    identities[str(path)] = path.read_text().split(') ', 1)[1].split()[19]
results = []
subprocess.run(['sudo', 'timedatectl', 'set-ntp', 'false'], check=True)
subprocess.run(['sudo', 'date', '-s', '2026-01-01 12:00:00'], check=True, stdout=subprocess.DEVNULL)
for arguments, mode, preference in (
    (['session', 'light'], 'light', 'light'),
    (['dark'], 'dark', 'dark'),
    (['session', 'light'], 'dark', 'dark'),
    (['session', 'auto'], 'light', 'auto'),
    (['dark'], 'dark', 'dark'),
    (['session', 'auto'], 'dark', 'dark'),
    (['session', 'light'], 'light', 'light'),
):
    subprocess.run([str(home / '.local/bin/mac-tahoe-theme-switch'), *arguments], check=True)
    for attempt in range(120):
        state = json.loads(state_path.read_text())
        qt = json.loads((probe / 'probe.json').read_text())
        gtk = [json.loads((probe / ('gtk' + version + '.json')).read_text()) for version in ('3', '4')]
        dark = mode == 'dark'
        alpha = .48 if dark else .55
        if (state.get('applied') == mode and state.get('preference') == preference
                and all(abs(qt[key]['alpha'] / 255 - alpha) < .02
                        and ((qt[key]['text'] > 128) == dark) for key in ('ordinary', 'system'))
                and all((sum(value['background'][:3]) < 1.5) == dark for value in gtk)):
            break
        time.sleep(.25)
    else:
        raise AssertionError((arguments, state, qt, gtk))
    for path, identity in identities.items():
        assert Path(path).read_text().split(') ', 1)[1].split()[19] == identity
    results.append({'arguments': arguments, 'state': state, 'qt': qt, 'gtk': gtk,
                    'process_identities': identities})
    print(' '.join(arguments), '->', mode, preference, 'passed', flush=True)
(home / 'appearance-session-results.json').write_text(json.dumps(results, indent=2))
