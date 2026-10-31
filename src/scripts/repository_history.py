"""Plan lightweight installation history without changing a development checkout.

SPDX-License-Identifier: GPL-3.0-or-later
"""
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import subprocess


PROJECTS = {'lestercorderomurillo/macos-tahoe-liquid-kde',
            'lestercorderomurillo/macos-golden-gate-liquid-kde'}
OID = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        return None
    return tuple(int(part) for part in value.split('.'))


@dataclass(frozen=True)
class PublishedSnapshot:
    """A published release plus its canonical remote ref advertisement.

    The resolver, not VERSION or a local tag, supplies this proof. Descendants
    are remote main/dev commits whose ancestry was verified on the server when
    their objects are not already available locally.
    """
    repository: str
    version: str
    commit: str
    refs: dict[str, str]
    descendants: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RefChange:
    name: str
    before: str
    after: str | None
    reason: str


@dataclass
class HistoryPlan:
    mode: str
    reason: str
    head: str = ''
    version: str = ''
    branch: str = ''
    refs: dict[str, str] = field(default_factory=dict)
    changes: list[RefChange] = field(default_factory=list)
    frontiers: list[str] = field(default_factory=list)


def git(repository, *args, input=None):
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env['GIT_OPTIONAL_LOCKS'] = '0'
    env['GIT_NO_LAZY_FETCH'] = '1'
    return subprocess.run(['git', '-c', 'maintenance.auto=false', '-c', 'gc.auto=0',
                           '-C', str(repository), *args], input=input, env=env,
                          encoding='utf-8', errors='surrogateescape', capture_output=True,
                          timeout=120, check=False)


def _ancestor(root, older, newer):
    return git(root, 'merge-base', '--is-ancestor', older, newer).returncode == 0


def _canonical_origin(url, repository):
    url = url.lower().rstrip('/').removesuffix('.git')
    return url in {f'https://github.com/{repository}', f'git@github.com:{repository}',
                   f'ssh://git@github.com/{repository}'}


def inspect_history(repository: Path, published: PublishedSnapshot | None) -> HistoryPlan:
    """Read-only audit; every uncertain or personal state remains unmodified."""
    root = Path(repository).resolve()
    plan = HistoryPlan('unverified', 'published-release-proof-required')
    if os.environ.get('GOLDEN_GATE_TAHOE_SOURCE'):
        return HistoryPlan('development', 'explicit-development-source')
    if published is None:
        return plan
    latest = version(published.version)
    tag = 'refs/tags/v' + published.version
    if (not isinstance(published.repository, str) or published.repository not in PROJECTS or latest is None
            or not isinstance(published.commit, str) or not OID.fullmatch(published.commit)
            or published.refs.get(tag + '^{}', published.refs.get(tag)) != published.commit):
        return plan
    directory = root / '.git'
    if directory.is_symlink() or not directory.is_dir():
        return HistoryPlan('unsupported', 'independent-checkout-required')
    if any((directory / path).is_symlink() for path in (
            'HEAD', 'config', 'index', 'shallow', 'packed-refs', 'refs', 'logs',
            'logs/refs/heads', 'objects', 'objects/pack')):
        return HistoryPlan('unsupported', 'shared-or-unusual-git-metadata')
    if any(path.is_symlink() for name in ('refs', 'logs') for path in (directory / name).rglob('*')):
        return HistoryPlan('unsupported', 'shared-or-unusual-git-metadata')
    if any((directory / path).exists() for path in ('worktrees', 'objects/info/alternates')):
        return HistoryPlan('unsupported', 'shared-object-store-or-worktree')
    try:
        return _inspect(root, directory, published, plan)
    except (OSError, ValueError, subprocess.SubprocessError):
        return HistoryPlan('unverified', 'could-not-complete-history-audit')


def _inspect(root, directory, published, plan):
    def reject(reason, mode='development'):
        plan.mode, plan.reason = mode, reason
        plan.changes.clear()
        plan.frontiers.clear()
        return plan

    def value(*args):
        result = git(root, *args)
        if result.returncode:
            raise ValueError('Git query failed')
        return result.stdout.strip()

    if Path(value('rev-parse', '--show-toplevel')).resolve() != root:
        return reject('not-checkout-root', 'unsupported')
    if git(root, 'config', '--get', 'extensions.refStorage').stdout.strip() not in ('', 'files'):
        return reject('unsupported-ref-storage', 'unsupported')
    if git(root, 'config', '--type=bool', '--get', 'extensions.preciousObjects').stdout.strip() == 'true':
        return reject('precious-objects')
    if any((directory / path).exists() for path in (
            'index.lock', 'shallow.lock', 'packed-refs.lock', 'config.lock',
            'MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge',
            'rebase-apply', 'sequencer', 'BISECT_LOG')):
        return reject('git-operation-in-progress', 'busy')
    if not _canonical_origin(value('remote', 'get-url', 'origin'), published.repository):
        return reject('development-remote')
    plan.head = value('rev-parse', 'HEAD')
    plan.branch = git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD').stdout.strip()
    if value('status', '--porcelain=v1', '-z', '--untracked-files=all'):
        return reject('local-files-in-progress')
    plan.version = (root / 'VERSION').read_text().strip()
    if version(plan.version) != version(published.version) or plan.head != published.commit:
        return reject('source-is-not-the-published-release')
    if plan.branch not in ('', 'main', 'dev'):
        return reject('working-on-a-development-branch')
    if value('show', published.commit + ':VERSION') != published.version:
        return reject('published-version-mismatch', 'unverified')

    records = value('for-each-ref', '--format=%(refname)%00%(objectname)%00%(*objectname)%00%(symref)')
    refs = {}
    symbolic = set()
    peeled = {}
    for record in records.splitlines():
        name, object_id, commit, target = record.split('\0')
        refs[name] = object_id
        peeled[name] = commit or object_id
        if target:
            symbolic.add(name)
    plan.refs = refs
    canonical = published.refs
    available = {line.split()[0] for line in value('cat-file', '--batch-all-objects',
                 '--batch-check=%(objectname)').splitlines()}

    def source_version(tip):
        tree = git(root, 'ls-tree', tip, '--', 'VERSION')
        fields = tree.stdout.split()
        if tree.returncode or len(fields) < 3 or fields[2] not in available:
            return None
        found = git(root, 'cat-file', 'blob', fields[2])
        return found.stdout.strip() if found.returncode == 0 else None
    def ancestor(older, newer):
        return older in available and newer in available and _ancestor(root, older, newer)

    published_commits = {published.commit}
    for name, object_id in canonical.items():
        if name.startswith('refs/tags/v') and not name.endswith('^{}'):
            number = version(name.removeprefix('refs/tags/v'))
            if number is not None and number <= version(published.version):
                tip = canonical.get(name + '^{}', object_id)
                number_at_tip = source_version(tip)
                if (OID.fullmatch(tip) and ancestor(tip, published.commit)
                        and version(number_at_tip) == number):
                    published_commits.add(tip)

    # Local and HEAD reflogs are user recovery data. Include OLD and NEW IDs;
    # `%H` alone misses the old side of the first recorded ref update.
    logs = [directory / 'logs/HEAD']
    if (directory / 'logs/refs/heads').is_dir():
        logs.extend(path for path in (directory / 'logs/refs/heads').rglob('*') if path.is_file())
    for path in logs:
        if path.is_symlink():
            return reject('unusual-recovery-log')
        if path.exists():
            for record in path.read_text(errors='surrogateescape').splitlines():
                fields = record.split(' ', 2)
                if len(fields) != 3:
                    return reject('unrecognized-recovery-log')
                for object_id in fields[:2]:
                    if not OID.fullmatch(object_id):
                        return reject('unrecognized-recovery-log')
                    if set(object_id) != {'0'} and not ancestor(object_id, published.commit):
                        return reject('unpublished-local-recovery-history')
    for name in ('ORIG_HEAD', 'FETCH_HEAD'):
        path = directory / name
        if path.is_symlink():
            return reject('unusual-recovery-ref')
        if path.is_file():
            for record in path.read_text(errors='surrogateescape').splitlines():
                object_id = record.split('\t', 1)[0]
                if not OID.fullmatch(object_id) or not ancestor(object_id, published.commit):
                    return reject('unpublished-recovery-ref')

    for name, object_id in refs.items():
        if name in symbolic:
            if name != 'refs/remotes/origin/HEAD':
                return reject('custom-symbolic-ref')
            continue
        tip = peeled[name]
        if name in ('refs/heads/main', 'refs/heads/dev'):
            if object_id != published.commit:
                branch = name.removeprefix('refs/heads/')
                if (object_id not in published_commits
                        or value('config', '--get', f'branch.{branch}.remote') != 'origin'
                        or value('config', '--get', f'branch.{branch}.merge') != 'refs/heads/' + branch):
                    return reject('local-branch-in-progress')
                # Keep main/dev positions and their normal pull semantics.
        elif name.startswith('refs/heads/'):
            number = version(source_version(object_id))
            if number is None or number >= version(published.version) or not ancestor(tip, published.commit):
                return reject('local-branch-in-progress')
            branch = name.removeprefix('refs/heads/')
            remote = git(root, 'config', '--get', f'branch.{branch}.remote').stdout.strip()
            upstream = git(root, 'config', '--get', f'branch.{branch}.merge').stdout.strip()
            upstream_tip = canonical.get(upstream) if remote == 'origin' else None
            if (remote and remote != 'origin') or (upstream_tip and not ancestor(upstream_tip, published.commit)):
                return reject('branch-tracks-unpublished-work')
            plan.changes.append(RefChange(name, object_id, None, 'merged-older-version-branch'))
        elif name.startswith('refs/tags/'):
            if canonical.get(name) != object_id:
                return reject('private-tag')
            # Canonical tags are tiny provenance metadata. Some older tags
            # precede VERSION conventions or belong to independent histories;
            # retain them and all their non-current objects.
        elif name.startswith('refs/remotes/origin/'):
            branch = name.removeprefix('refs/remotes/origin/')
            remote_name = 'refs/heads/' + branch
            if branch in ('main', 'dev'):
                remote_tip = canonical.get(remote_name)
                if not remote_tip or not (ancestor(published.commit, remote_tip)
                                          or remote_tip in published.descendants):
                    return reject('remote-role-ancestry-unverified', 'unverified')
                if object_id != remote_tip:
                    if not ancestor(object_id, published.commit):
                        return reject('unpublished-cached-role')
                    # Preserve cached main/dev positions.
            else:
                if object_id != canonical.get(remote_name):
                    return reject('unpublished-cached-branch')
                number = version(source_version(object_id))
                if ancestor(object_id, published.commit) and number is not None and number < version(published.version):
                    plan.changes.append(RefChange(name, object_id, None, 'merged-older-remote-cache'))
        else:
            return reject('private-ref')

    # Do not reinterpret abandoned blobs/commits as cache. This also catches
    # private old reflog roots that no longer have a corresponding log file.
    checked = git(root, 'fsck', '--full', '--unreachable', '--no-reflogs')
    public = {line.split()[0].removeprefix('?') for line in
              value('rev-list', '--objects', '--missing=print', published.commit).splitlines()}
    recovery = {line.split()[2] for line in checked.stdout.splitlines()
                if line.startswith(('unreachable ', 'dangling ')) and len(line.split()) == 3}
    # fsck stops traversal at promisor objects and can label their already
    # public ancestors unreachable. Only canonical reachability proves cache.
    if checked.returncode or recovery - public:
        return reject('unreferenced-recovery-objects')
    plan.mode, plan.reason = 'installation', 'verified-clean-published-source'
    # No shallow boundary: retain the complete commit/tree graph.
    return plan
