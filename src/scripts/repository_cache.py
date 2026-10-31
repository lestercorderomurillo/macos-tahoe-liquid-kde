"""Retire only published Git file caches, retaining the complete ancestry.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import urllib.request
import uuid

from repository_history import PROJECTS, PublishedSnapshot, git, inspect_history, version

HINTS = 'MAC_TAHOE_RELEASE_HINTS'
SMALL_BLOB = 64 * 1024


def hint(repository, latest):
    """Pass this launch's update result across exec, including offline failure."""
    try:
        hints = json.loads(os.environ.get(HINTS, '{}'))
        if not isinstance(hints, dict):
            hints = {}
    except ValueError:
        hints = {}
    hints[repository] = latest.removeprefix('v') if isinstance(latest, str) else None
    os.environ[HINTS] = json.dumps(hints)


def _checked(root, *args, input=None):
    result = git(root, *args, input=input)
    if result.returncode:
        raise ValueError(result.stderr.strip() or 'Git query failed')
    return result.stdout.strip()


def canonical_project(root):
    directory = root / '.git'
    if (not directory.is_dir() or directory.is_symlink()
            or any((directory / path).exists() for path in ('worktrees', 'objects/info/alternates'))):
        return None
    origin = _checked(root, 'remote', 'get-url', 'origin').lower().rstrip('/').removesuffix('.git')
    for repository in PROJECTS:
        if origin in (f'https://github.com/{repository}', f'git@github.com:{repository}',
                      f'ssh://git@github.com/{repository}'):
            return repository
    return None


def published_snapshot(root, repository):
    """Never trust VERSION or a local tag as evidence of publication."""
    if (os.environ.get('GOLDEN_GATE_TAHOE_SOURCE')
            or os.environ.get('MAC_TAHOE_NO_UPDATE_CHECK', '').lower() == 'true'):
        return None
    try:
        hints = json.loads(os.environ.get(HINTS, '{}'))
        if repository in hints:
            latest = hints[repository]
        else:
            request = urllib.request.Request(f'https://api.github.com/repos/{repository}/releases/latest',
                       headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'mac-tahoe-installer'})
            with urllib.request.urlopen(request, timeout=5) as response:
                release = json.loads(response.read(1024 * 1024))
            latest = release.get('tag_name', '').removeprefix('v')
        if version(latest) is None or (root / 'VERSION').read_text().strip() != latest:
            return None
        advertisement = _checked(root, 'ls-remote', f'https://github.com/{repository}.git',
                                 'refs/heads/*', 'refs/tags/*')
        refs = {}
        for record in advertisement.splitlines():
            oid, name = record.split('\t')
            if not re.fullmatch('[0-9a-f]{40}', oid) or not name.startswith('refs/'):
                return None
            refs[name] = oid
        tag = 'refs/tags/v' + latest
        commit = refs.get(tag + '^{}', refs.get(tag))
        if commit != _checked(root, 'rev-parse', 'HEAD'):
            return None
        return PublishedSnapshot(repository, latest, commit, refs)
    except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError):
        return None


def _stamp(path):
    stat = path.lstat()
    return [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns]


def _signature(root):
    directory = root / '.git'
    records = {}
    for name in ('HEAD', 'index', 'config', 'packed-refs', 'shallow', 'ORIG_HEAD', 'FETCH_HEAD'):
        path = directory / name
        if path.exists():
            records[name] = _stamp(path)
    for name in ('refs', 'logs', 'objects'):
        for path in (directory / name).rglob('*'):
            if path.is_file() and not path.name.endswith('.lock'):
                records[str(path.relative_to(directory))] = _stamp(path)
    records['status'] = _checked(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all')
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()


def _write_json(path, value):
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.maintenance-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, path)
            fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            temporary.unlink(missing_ok=True)


def _recover_owned_locks(directory):
    """Recover only our marked locks after their recorded process has exited."""
    owner_path = directory / 'tahoe-maintenance-owner.json'
    try:
        owner = json.loads(owner_path.read_text())
        pid = owner['pid']
        token = owner['token']
        if not isinstance(pid, int) or pid <= 0 or not re.fullmatch('[0-9a-f]{32}', token):
            return
        try:
            os.kill(pid, 0)
            return  # A live or reused PID is conservative: never steal its locks.
        except ProcessLookupError:
            pass
        except PermissionError:
            return
        allowed = {'index.lock', 'HEAD.lock', 'gc.pid', 'config.lock',
                   'refs/heads/main.lock', 'refs/heads/dev.lock'}
        marker = ('# tahoe-maintenance-owner ' + token).encode()
        for name in owner['paths']:
            if name not in allowed:
                continue
            path = directory / name
            if path.is_file() and not path.is_symlink() and path.stat().st_size < 1024 * 1024:
                if marker in path.read_bytes().splitlines():
                    path.unlink()
        owner_path.unlink(missing_ok=True)
    except (OSError, ValueError, KeyError, TypeError):
        return


def recover_interrupted_maintenance(directory):
    descriptor = os.open(directory / 'tahoe-maintenance.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _recover_owned_locks(directory)
    finally:
        os.close(descriptor)


@contextlib.contextmanager
def _lease(directory, branch):
    """Share Git's writer locks; never steal a lock from another process."""
    owned = []
    recorded = False
    token = uuid.uuid4().hex
    marker = '# tahoe-maintenance-owner ' + token
    owner_path = directory / 'tahoe-maintenance-owner.json'
    descriptor = os.open(directory / 'tahoe-maintenance.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _recover_owned_locks(directory)
        if owner_path.exists():
            raise BlockingIOError('Previous maintenance owner is still active')
        names = ['index.lock', 'HEAD.lock', 'gc.pid', 'config.lock', 'refs/heads/' + branch + '.lock']
        _write_json(owner_path, {'pid': os.getpid(), 'token': token, 'paths': names})
        recorded = True
        for name in names:
            path = directory / name
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            owned.append((path, os.fstat(fd).st_ino))
            with os.fdopen(fd, 'w') as stream:
                if name == 'gc.pid':
                    stream.write(f'{os.getpid()} {socket.gethostname()}\n')
                stream.write(marker + '\n')
                stream.flush()
                os.fsync(stream.fileno())
        yield marker
    finally:
        for path, inode in reversed(owned):
            if path.exists() and path.lstat().st_ino == inode:
                path.unlink()
        if recorded:
            owner_path.unlink(missing_ok=True)
        os.close(descriptor)


def trim_published_cache(repository, *, automatic=False):
    """Return a report; uncertainty leaves the ordinary Git store intact.

    Only canonical public blobs may become lazy, remote-backed objects. All
    commit/tree/tag metadata, small historical sources, current branch trees,
    private objects and recovery records stay local. No shallow boundaries,
    reflog expiry, gc or forced prune is used.
    """
    root = Path(repository).resolve()
    result = {'status': 'skipped', 'reason': 'not-a-verified-installation', 'evicted_blobs': 0}
    try:
        project = canonical_project(root)
        if not project or os.environ.get('GOLDEN_GATE_TAHOE_SOURCE'):
            return result
        if os.environ.get('MAC_TAHOE_NO_UPDATE_CHECK', '').lower() == 'true':
            return result
        directory = root / '.git'
        recover_interrupted_maintenance(directory)
        policy = git(root, 'config', '--get', 'tahoe.maintenance').stdout.strip()
        if policy in ('off', 'compact'):
            return dict(result, reason='user-maintenance-policy')
        if git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD').stdout.strip() not in ('main', 'dev'):
            return dict(result, reason='working-on-a-development-branch')
        receipt = directory / 'tahoe-maintenance.json'
        signature = _signature(root)
        try:
            previous = json.loads(receipt.read_text())
        except (OSError, ValueError):
            previous = {}
        if automatic and previous.get('signature') == signature:
            return dict(result, reason='unchanged-object-cache')
        proof = published_snapshot(root, project)
        plan = inspect_history(root, proof)
        if plan.mode != 'installation' or not plan.branch:
            return dict(result, reason=plan.reason)
        # Shallow/shared/externally managed stores need their own policy.
        store = directory / 'objects'
        packs = store / 'pack'
        if ((directory / 'shallow').exists() or (packs / 'multi-pack-index.d').exists()
                or any(packs.glob('*.keep')) or any(path.is_symlink() for path in store.rglob('*'))):
            return dict(result, reason='externally-managed-object-store')
        partial = git(root, 'config', '--get', 'extensions.partialClone').stdout.strip()
        if partial not in ('', 'origin'):
            return dict(result, reason='another-partial-clone-remote')
        filtering = git(root, 'config', '--get', 'remote.origin.partialclonefilter').stdout.strip()
        if filtering not in ('', 'blob:none'):
            return dict(result, reason='another-partial-clone-filter')
        # The second audit ran before taking standard Git locks. Recheck its
        # exact read-only state under them, without having to ignore our locks.
        stable = _signature(root)
        with _lease(directory, plan.branch) as owner_marker:
            if _signature(root) != stable:
                return dict(result, reason='concurrent-git-change')
            # Snapshot complete immutable pack pairs BEFORE cataloging. A
            # concurrent fetch/index-pack may install new private packs while
            # cataloging; those must never enter this retirement set.
            complete = {path.stem for path in packs.glob('pack-*.pack')
                        if path.with_suffix('.idx').is_file()}
            old_files = {path: _stamp(path) for path in packs.iterdir() if path.is_file()
                         and (path.name.split('.', 1)[0] in complete or
                              path.name.startswith('multi-pack-index'))}
            catalog = {}
            for line in _checked(root, 'cat-file', '--batch-all-objects',
                                 '--batch-check=%(objectname) %(objecttype) %(objectsize)').splitlines():
                oid, kind, size = line.split()
                catalog[oid] = (kind, int(size))
            public = {line.split()[0].removeprefix('?') for line in
                      _checked(root, 'rev-list', '--objects', '--missing=print', proof.commit).splitlines()}
            keep = set(catalog) - public
            protected_tips = set()
            required_tips = set()
            keep.update(oid for oid, (kind, size) in catalog.items() if kind == 'blob' and size <= SMALL_BLOB)
            retired = {change.name for change in plan.changes}
            for ref in plan.refs:
                if ref not in retired and ref.startswith(('refs/heads/', 'refs/remotes/')):
                    tree = git(root, 'ls-tree', '-r', ref)
                    if tree.returncode:
                        raise ValueError('Cannot protect a branch snapshot')
                    objects = {line.split()[2] for line in tree.stdout.splitlines() if not line.startswith('160000 ')}
                    protected_tips.update(objects)
                    if ref.startswith('refs/heads/'):
                        required_tips.update(objects)
            required_tips.update(line.split()[2] for line in _checked(root, 'ls-tree', '-r', 'HEAD').splitlines()
                                 if not line.startswith('160000 '))
            protected_tips.update(required_tips)
            # Remote-only branches are metadata caches, not checked-out work.
            # Protect all their locally present files without forcing absent
            # filtered blobs online or blocking maintenance after every fetch.
            if required_tips - set(catalog):
                return dict(result, reason='branch-snapshot-not-local')
            keep.update(protected_tips)
            # Avoid lazy-fetching a currently absent branch snapshot.
            metadata = {oid for oid, (kind, size) in catalog.items() if oid in public and kind != 'blob'}
            # Retain the existing promise classification of fetched metadata.
            # Remote-only trees may already promise absent blobs; repacking
            # those trees as ordinary objects would make fsck report damage.
            for marker in [path for path in old_files if path.suffix == '.promisor']:
                with marker.with_suffix('.idx').open('rb') as index:
                    listed = git(root, 'show-index', stdin=index)
                if listed.returncode:
                    raise ValueError('Cannot inspect existing promised metadata')
                for line in listed.stdout.splitlines():
                    oid = line.split()[1]
                    if oid in catalog and catalog[oid][0] != 'blob':
                        metadata.add(oid)
            keep.intersection_update(catalog)
            keep.difference_update(metadata)
            evict = set(catalog) - metadata - keep
            if any(catalog[oid][0] != 'blob' or oid not in public for oid in evict):
                raise ValueError('Attempted to evict an unverified object')
            original_config = (directory / 'config').read_text()
            journal = {'schema': 1, 'repository': project, 'commit': proof.commit,
                       'version': proof.version, 'config_before': original_config,
                       'retired_refs': [{'name': change.name, 'object': change.before,
                         'reflog': (directory / 'logs' / change.name).read_text()
                           if (directory / 'logs' / change.name).is_file() else ''}
                           for change in plan.changes], 'phase': 'preparing'}
            # Preserve all earlier retired branch recovery records, including
            # records from an interrupted transaction. This is tiny metadata.
            journal_path = directory / 'tahoe-maintenance-journal.json'
            try:
                earlier = json.loads(journal_path.read_text()).get('retired_refs', [])
            except FileNotFoundError:
                earlier = []
            except (OSError, ValueError, AttributeError):
                return dict(result, reason='unrecognized-maintenance-journal')
            if not isinstance(earlier, list) or any(not isinstance(item, dict) or
                    not isinstance(item.get('name'), str) or not isinstance(item.get('object'), str)
                    or not isinstance(item.get('reflog'), str) for item in earlier):
                return dict(result, reason='unrecognized-maintenance-journal')
            identities = {(item['name'], item['object']) for item in journal['retired_refs']}
            journal['retired_refs'].extend(item for item in earlier if
                (item['name'], item['object']) not in identities)
            _write_json(journal_path, journal)
            if evict:
                new_prefixes = set()
                for objects, promisor in ((metadata, True), (keep, False)):
                    if not objects:
                        continue
                    packed = _checked(root, 'pack-objects', '--threads=1', str(packs / 'pack'),
                                      input='\n'.join(sorted(objects)) + '\n')
                    if not re.fullmatch('[0-9a-f]{40}', packed):
                        raise ValueError('Unexpected pack identity')
                    prefix = 'pack-' + packed
                    new_prefixes.add(prefix)
                    if promisor:
                        (packs / (prefix + '.promisor')).touch()
                    # Git fsync policy differs across versions; ensure pack bytes
                    # reach disk before any old copy can be retired.
                    for suffix in ('.pack', '.idx', '.promisor'):
                        path = packs / (prefix + suffix)
                        if path.exists():
                            with path.open('rb') as stream:
                                os.fsync(stream.fileno())
                pack_directory = os.open(packs, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(pack_directory)
                finally:
                    os.close(pack_directory)
                if (_checked(root, 'rev-parse', 'HEAD') != plan.head
                        or _checked(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all')
                        or (directory / 'config').read_text() != original_config
                        or (directory / 'worktrees').exists() or (store / 'info/alternates').exists()
                        or _checked(root, 'for-each-ref', '--format=%(refname) %(objectname)') !=
                           '\n'.join(name + ' ' + oid for name, oid in sorted(plan.refs.items()))):
                    return dict(result, reason='concurrent-source-change')
                config = directory / 'config.lock'
                with tempfile.TemporaryDirectory(prefix='maintenance-config-', dir=directory) as temporary:
                    staged = Path(temporary) / 'config'
                    staged.write_text(''.join(line for line in original_config.splitlines(keepends=True)
                                             if not re.fullmatch(r'# tahoe-maintenance-owner [0-9a-f]{32}\n?', line)))
                    for key, value in {'core.repositoryformatversion': '1', 'extensions.partialClone': 'origin',
                                       'remote.origin.promisor': 'true',
                                       'remote.origin.partialclonefilter': 'blob:none'}.items():
                        _checked(root, 'config', '--file', str(staged), key, value)
                    # Keep the owner marker intact even if writing is killed.
                    with config.open('ab') as stream:
                        stream.write(staged.read_bytes())
                with config.open('rb') as stream:
                    os.fsync(stream.fileno())
                os.replace(config, directory / 'config')
                journal['phase'] = 'remote-backed'
                _write_json(directory / 'tahoe-maintenance-journal.json', journal)
                # Derived indexes cannot outlive the pack set they describe.
                for path, stamp in old_files.items():
                    if path.name.startswith('multi-pack-index') and path.exists() and _stamp(path) == stamp:
                        path.unlink()
                for path, stamp in old_files.items():
                    prefix = path.name.split('.', 1)[0]
                    if (prefix not in new_prefixes
                            and not (packs / (prefix + '.keep')).exists()
                            and re.fullmatch(r'pack-[0-9a-f]{40}\.(?:pack|idx|rev|bitmap|promisor|mtimes)', path.name)
                            and path.exists() and _stamp(path) == stamp):
                        path.unlink()
                for oid in evict:
                    path = store / oid[:2] / oid[2:]
                    if path.is_file():
                        path.unlink()
                _checked(root, 'prune-packed')  # Only redundant loose copies.
            # CAS all retired branches in a single Git ref transaction. A
            # concurrent new branch/commit is never overwritten or deleted.
            if plan.changes:
                instructions = ['start']
                instructions.extend('delete ' + item.name + ' ' + item.before for item in plan.changes)
                instructions.extend(['prepare', 'commit', ''])
                _checked(root, 'update-ref', '--stdin', input='\n'.join(instructions))
            journal['phase'] = 'complete'
            _write_json(directory / 'tahoe-maintenance-journal.json', journal)
        _write_json(receipt, {'signature': _signature(root), 'commit': proof.commit})
        return dict(result, status='ok', reason='published-file-cache-retired', evicted_blobs=len(evict),
                    retired_branches=len(plan.changes))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return dict(result, status='skipped', reason=str(exc))
