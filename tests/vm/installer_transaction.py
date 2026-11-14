"""Actual backend lock and install/reinstall qualification in a disposable VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src/installer'), str(ROOT / 'src/scripts')]


def main():
    if Path('/sys/class/dmi/id/product_name').read_text().strip() != 'MTTKDE release capture':
        raise SystemExit('A disposable release-capture VM is required')
    if os.geteuid() == 0:
        raise SystemExit('Run as the guest desktop user; only the backend uses sudo')
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    backend = str(ROOT / 'src/scripts/installer_backend.py')
    lock_probe = '''
import subprocess, sys
from installer_lock import installer_lock
with installer_lock():
    result = subprocess.run([sys.executable, sys.argv[1], 'install', '--only', '--no-apply-theme'], capture_output=True, text=True)
    assert result.returncode == 2, result
    assert 'Another installation or removal is running' in result.stderr, result
print('Concurrent backend refused before installation')
'''
    state = Path.home() / '.local/state/mac-tahoe-liquid-kde/last-run.json'
    before = state.read_bytes() if state.exists() else None
    probe = subprocess.run(['sudo', '-n', 'env', 'PYTHONPATH=' + str(ROOT / 'src/scripts'),
                            'python3', '-c', lock_probe, backend], cwd=ROOT, capture_output=True, text=True, check=True)
    assert (state.read_bytes() if state.exists() else None) == before
    (args.output / 'overlap.log').write_text(probe.stdout + probe.stderr)
    runs = []
    for name in ('install', 'reinstall'):
        fd, progress = tempfile.mkstemp(prefix='installer-qualification-', dir=args.output)
        os.close(fd)
        log_path = args.output / (name + '.log')
        command = ['sudo', '-n', 'env', 'MAC_TAHOE_NO_UPDATE_CHECK=true', 'MTTKDE_NO_CONFIRM=1',
                   'PYTHONUNBUFFERED=1', 'MTTKDE_LANGUAGE=en', 'MTTKDE_PROGRESS_FILE=' + progress,
                   'MTTKDE_WIZARD_OPTIONS={"appearance":"light","reset_layout":false}',
                   'python3', backend, 'install', '--only', '--no-apply-theme', '--light']
        with log_path.open('w') as output:
            result = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=300)
        assert result.returncode == 0, log_path.read_text()[-6000:]
        records = Path(progress).read_text().splitlines()
        assert records.count('__DONE__\t0') == 1, records
        from progress_model import ProgressModel
        summary = ProgressModel()
        for record in records:
            if record.startswith('__EVENT__\t'):
                summary.accept(json.loads(record.split('\t', 1)[1]))
        summary.finish(result.returncode)
        for key in ('system', 'dependencies', 'install'):
            assert summary.phases[key]['state'] == 'done', summary.phases
        for key in ('downloads', 'build', 'apply', 'verify'):
            assert summary.phases[key]['state'] == 'skipped', summary.phases
        text = log_path.read_text()
        assert 'Developed by Lester' not in text and 'auto-accepting' not in text
        runs.append({'name': name, 'command': command, 'exit_code': result.returncode,
                     'summary': summary.text(), 'log_sha256': hashlib.sha256(log_path.read_bytes()).hexdigest(),
                     'progress_sha256': hashlib.sha256(Path(progress).read_bytes()).hexdigest()})
    files = ('VERSION', 'component-hashes.json', 'src/scripts/defaults.json',
             'src/installer/installer_ui.py', 'src/installer/progress_model.py', 'src/installer/wizard_window.py',
             'src/scripts/cli.py', 'src/scripts/log.py', 'src/scripts/installer_backend.py', 'src/scripts/installer_lock.py')
    evidence = {'runs': runs, 'overlap': 'passed',
                'source_files': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
                'limits': 'Actual focused backend install/reinstall without desktop activation. Representative progress/error/completion UI frames are recorded separately; this is not a full desktop reinstall.'}
    (args.output / 'qualification.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print('Backend overlap, install and reinstall passed:', args.output)


if __name__ == '__main__':
    main()
