"""Reversible installation of user-directory assets, with content ownership.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from component_cache import fingerprint
from log import warn


def _exists(path):
    return path.exists() or path.is_symlink()


def _plain_parents(path):
    if any(p.is_symlink() for p in path.parents):
        raise OSError(f"Refusing asset path through a symbolic link: {path}")


def _entry(component, target):
    target = Path(os.path.abspath(target))
    state = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state')
    root = state / 'mac-tahoe-liquid-kde/owned-assets' / component
    _plain_parents(root / 'entry')
    key = hashlib.sha256(str(target).encode()).hexdigest()
    return target, root, root / (key + '.json')


def _read(path, target):
    if path.is_symlink():
        raise OSError('Unsafe asset ownership record')
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    if data.get('target') != str(target) or not isinstance(data.get('fingerprint'), str):
        raise ValueError('Invalid asset ownership record')
    backups = data.get('backups', [])
    if not isinstance(backups, list) or any(not isinstance(n, str) or Path(n).name != n or not n.startswith('backup-') for n in backups):
        raise ValueError('Invalid asset recovery record')
    return data


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as f:
        json.dump(data, f)
        temporary = Path(f.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _remove(path):
    if path.is_symlink() or not path.is_dir():
        path.unlink()
    else:
        shutil.rmtree(path)


def install(component, source, target, copier):
    """Back up preexisting/edited payloads before replacement; never claim names."""
    target, root, record = _entry(component, target)
    _plain_parents(target)
    previous = _read(record, target)
    backups = list(previous.get('backups', [])) if previous else []
    exists = _exists(target)
    changed = exists and (previous is None or fingerprint(target) != previous['fingerprint'])
    saved = None
    if changed:
        root.mkdir(parents=True, exist_ok=True)
        saved = root / ('backup-' + uuid.uuid4().hex)
        # Copy first: an unsuccessful copy cannot remove the user's original.
        if target.is_symlink():
            saved.symlink_to(target.readlink())
        elif target.is_dir():
            shutil.copytree(target, saved, symlinks=True)
        else:
            shutil.copy2(target, saved)
        backups.append(saved.name)
    try:
        result = copier(source, target)
        if result is False:
            raise OSError(f'Asset installation failed: {target}')
        _save(record, dict(target=str(target), fingerprint=fingerprint(target), backups=backups))
    except BaseException:
        # A successful replacement with a failed receipt must retain its backup.
        if saved is not None:
            warn(f'Original asset retained at {saved}')
        raise
    return result


def remove_owned(component, base):
    """Leave modified/unrecorded assets intact. Restore the latest user baseline."""
    base = Path(os.path.abspath(base))
    _, root, _ = _entry(component, base)
    removed = 0
    for record in root.glob('*.json'):
        data = json.loads(record.read_text())
        target = Path(data.get('target', ''))
        if (not target.is_absolute() or target != Path(os.path.abspath(target))
                or target == base or not target.is_relative_to(base)):
            raise ValueError('Asset record escapes destination')
        _plain_parents(target)
        data = _read(record, target)
        if _exists(target) and fingerprint(target) != data['fingerprint']:
            warn(f'Preserving modified asset: {target}')
            continue
        backups = data.get('backups', [])
        if backups:
            saved = root / backups[-1]
            if not _exists(saved):
                raise OSError(f'Missing original asset backup: {saved}')
            # Restore using an atomic per-file replacement or the existing
            # rollback-capable directory copier. Keep older recovery copies.
            if saved.is_symlink():
                if _exists(target):
                    _remove(target)
                target.symlink_to(saved.readlink())
            elif saved.is_dir():
                from utils import safe_copy
                if not safe_copy(saved, target):
                    raise OSError(f'Could not restore original asset: {target}')
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                fd, name = tempfile.mkstemp(dir=target.parent)
                os.close(fd)
                temporary = Path(name)
                try:
                    shutil.copy2(saved, temporary)
                    os.replace(temporary, target)
                finally:
                    temporary.unlink(missing_ok=True)
            _remove(saved)
        elif _exists(target):
            _remove(target)
        if len(backups) > 1:
            _save(record.with_suffix(".recovery"), dict(
                target=str(target), backups=backups[:-1],
                detail="Earlier user versions retained after restoring the latest baseline"))
        record.unlink()
        removed += 1
    return removed
