"""Content identities and success receipts for independently installed payloads.

SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile


def fingerprint(path: Path, *, portable: bool = False) -> str:
    """Hash names, types, permissions, bytes and link targets, never follow links."""
    value = hashlib.sha256()
    def visit(item, relative):
        metadata = item.lstat()
        mode = stat.S_IMODE(metadata.st_mode)
        if stat.S_ISLNK(metadata.st_mode):
            kind, data = 'link', os.readlink(item).encode()
        elif stat.S_ISDIR(metadata.st_mode):
            kind, data = 'directory', b''
        elif stat.S_ISREG(metadata.st_mode):
            kind, data = 'file', b''
        else:
            raise ValueError(f'Unsupported component entry: {item}')
        if portable:
            mode = 0o777 if kind == 'link' else (0o755 if kind == 'directory' or mode & 0o111 else 0o644)
        header = json.dumps([relative, kind, mode], separators=(',', ':')).encode()
        value.update(len(header).to_bytes(8, 'big')); value.update(header)
        if kind == 'file':
            value.update(metadata.st_size.to_bytes(8, 'big'))
            with item.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    value.update(chunk)
        else:
            value.update(len(data).to_bytes(8, 'big')); value.update(data)
        if kind == 'directory':
            for child in sorted(item.iterdir()):
                visit(child, relative + '/' + child.name)
    visit(Path(path), '.')
    return value.hexdigest()


def identical(source: Path, destination: Path) -> bool:
    try:
        return fingerprint(source) == fingerprint(destination)
    except (OSError, ValueError):
        return False


def identity(paths, options=None, *, portable=False):
    records = [(str(name), fingerprint(path, portable=portable)) for name, path in paths]
    return hashlib.sha256(json.dumps([records, options], sort_keys=True).encode()).hexdigest()


class Receipt:
    """An optimization only: malformed, missing or changed evidence is a miss."""
    def __init__(self, component, key, root=None):
        state = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state')
        self.path = (Path(root) if root is not None else state / 'mac-tahoe-liquid-kde/components') / (hashlib.sha256(component.encode()).hexdigest() + '.json')
        self.component, self.key = component, key

    def current(self, outputs):
        try:
            record = json.loads(self.path.read_text())
            if (not isinstance(record, dict) or record.get('schema') != 1
                    or record.get('component') != self.component or record.get('key') != self.key):
                return False
            paths = list(outputs)
            return bool(paths) and record == self.record(paths)
        except (OSError, ValueError, TypeError):
            return False

    def record(self, outputs):
        return dict(schema=1, component=self.component, key=self.key,
                    outputs={str(path): fingerprint(path) for path in outputs})

    def invalidate(self):
        self.path.unlink(missing_ok=True)

    def save(self, outputs):
        paths = list(outputs)
        if not paths:
            return
        record = self.record(paths)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=self.path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(record, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
