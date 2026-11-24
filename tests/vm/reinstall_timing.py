"""Measure an unchanged wizard-backend reinstall in a prepared Plasma VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    output = parser.parse_args().output
    if Path('/sys/class/dmi/id/product_name').read_text().strip() != 'MTTKDE release capture':
        parser.error('A disposable release-capture VM is required')
    if os.geteuid() == 0:
        parser.error('Run as the guest desktop user')
    state = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state')
    last = json.loads((state / 'mac-tahoe-liquid-kde/last-run.json').read_text())
    args = last['argv']
    if (last['script'] != 'install' or last['status'] != 'completed' or last['exit_code'] != 0
            or len(args) != 2 or args[0] != '--wizard-options'):
        parser.error('Seed the guest with a successful full wizard-backend install first')
    choices = json.loads(args[1])
    if choices.get('reset_layout') is not False:
        parser.error('Seed the guest with layout reset disabled for an unchanged reinstall')
    output.mkdir(parents=True, exist_ok=True)
    command = ['sudo', '-n', 'env', 'MTTKDE_NO_CONFIRM=1', 'MAC_TAHOE_NO_UPDATE_CHECK=true',
               str(ROOT / 'src/scripts/installer_backend.py'), 'install', *args]
    with (output / 'reinstall.log').open('w') as log:
        start = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=600)
        seconds = time.monotonic() - start
    report = {'seconds': seconds, 'limit_seconds': 10, 'exit_code': result.returncode,
              'choices': choices, 'version': (ROOT / 'VERSION').read_text().strip(),
              'component_manifest_sha256': hashlib.sha256((ROOT / 'component-hashes.json').read_bytes()).hexdigest(),
              'passed': result.returncode == 0 and seconds < 10}
    (output / 'timing.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Unchanged reinstall took {seconds:.3f}s (target <10s, exit {result.returncode})')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
